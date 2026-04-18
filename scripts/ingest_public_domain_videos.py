"""
Ingest public-domain / CC0 educational videos into the video library as
self-hosted content.

Unlike ingest_youtube_catalog.py which only embeds, this script:
  1. Downloads MP4s from the source URL
  2. Uploads them to S3 (bucket: lulia-generated, key: library/pd/{uuid}.mp4)
  3. Creates a videos row with hosting_type='self_hosted', source_lane='oer_public_domain'
  4. Fires Inngest video/upload.completed event so existing post-processing
     pipeline (ffprobe, thumbnail, transcribe, classify, align) runs automatically

Uses the same manifest pattern as ingest_local_references.py: a JSON manifest
under data/video_library/ lists each source with metadata.

Install requirements (already in container):
    # httpx is already installed for import_standards.py

Usage:
    docker compose exec api python scripts/ingest_public_domain_videos.py --manifest public_domain.json
    docker compose exec api python scripts/ingest_public_domain_videos.py --manifest public_domain.json --limit 5 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, "/app")

import boto3
import httpx

from src.lms_agents.tools.db import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
log = logging.getLogger("ingest_public_domain")

_BUCKET = "lulia-generated"
MANIFEST_DIR = Path("/app/data/video_library")


def _get_s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )


def download_and_upload(source: dict) -> str | None:
    """Download MP4 from source_url, upload to S3. Returns the S3 key."""
    mp4_url = source.get("mp4_url")
    if not mp4_url:
        log.warning("  %s: no mp4_url, skipping", source.get("id"))
        return None

    video_id = str(uuid4())
    s3_key = f"library/pd/{video_id}.mp4"

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        log.info("  Downloading: %s", mp4_url)
        with httpx.stream("GET", mp4_url, follow_redirects=True, timeout=300) as r:
            r.raise_for_status()
            with open(tmp_path, "wb") as f:
                total = 0
                for chunk in r.iter_bytes(chunk_size=1024 * 256):
                    f.write(chunk)
                    total += len(chunk)
        size_mb = os.path.getsize(tmp_path) / 1e6
        log.info("  Downloaded %.1f MB", size_mb)

        s3 = _get_s3()
        s3.upload_file(tmp_path, _BUCKET, s3_key, ExtraArgs={"ContentType": "video/mp4"})
        log.info("  Uploaded to s3://%s/%s", _BUCKET, s3_key)
        return s3_key, video_id
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def source_exists(cur, source_url: str) -> bool:
    cur.execute(
        "SELECT 1 FROM videos WHERE source_url = %s AND source_lane = 'oer_public_domain' LIMIT 1",
        (source_url,),
    )
    return cur.fetchone() is not None


def insert_video(cur, source: dict, s3_key: str, video_id: str):
    """Insert a self-hosted public-domain video in 'processing' state."""
    cur.execute(
        """
        INSERT INTO videos
          (video_id, title, file_url,
           hosting_type, source_lane, scope,
           subject, grade_level, attribution, license, source_url,
           status)
        VALUES (%s::uuid, %s, %s,
                'self_hosted', 'oer_public_domain', 'public',
                %s, %s, %s, %s, %s,
                'processing')
        """,
        (
            video_id,
            source.get("title") or source.get("id"),
            s3_key,
            source.get("subject"),
            source.get("grade_hint"),
            source.get("attribution"),
            source.get("license") or "Public Domain",
            source.get("source_url"),
        ),
    )


def _fire_processing_event(video_id: str, s3_key: str):
    """Trigger the existing video/upload.completed pipeline."""
    import asyncio
    import inngest
    from src.lms_agents.inngest.client import inngest_client

    async def _send():
        await inngest_client.send(
            inngest.Event(
                name="video/upload.completed",
                data={"video_id": video_id, "s3_key": s3_key},
            )
        )

    asyncio.run(_send())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=str, required=True,
                    help="JSON manifest filename under data/video_library/")
    ap.add_argument("--limit", type=int, default=None, help="Process at most N sources")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manifest_path = MANIFEST_DIR / args.manifest
    if not manifest_path.exists():
        log.error("Manifest not found: %s", manifest_path)
        sys.exit(1)

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    sources = manifest.get("sources", [])
    if args.limit:
        sources = sources[: args.limit]

    log.info("Manifest: %s (%d sources)", manifest_path.name, len(sources))

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    failed = 0
    try:
        for i, source in enumerate(sources, 1):
            source_url = source.get("source_url") or ""
            log.info("[%d/%d] %s", i, len(sources), source.get("id") or source_url)

            if source_url and source_exists(cur, source_url):
                log.info("  Already ingested, skipping")
                skipped += 1
                continue

            if args.dry_run:
                log.info("  [dry] would download %s and upload to S3", source.get("mp4_url"))
                inserted += 1
                continue

            try:
                result = download_and_upload(source)
                if not result:
                    failed += 1
                    continue
                s3_key, video_id = result

                insert_video(cur, source, s3_key, video_id)
                conn.commit()
                inserted += 1

                try:
                    _fire_processing_event(video_id, s3_key)
                except Exception as e:
                    log.debug("Inngest event skipped: %s", e)
            except Exception as e:
                log.error("  Failed: %s", e)
                failed += 1
                conn.rollback()

    finally:
        cur.close()
        conn.close()

    log.info("=" * 60)
    log.info("inserted=%d skipped=%d failed=%d", inserted, skipped, failed)


if __name__ == "__main__":
    main()
