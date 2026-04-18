"""
Ingest curated educational YouTube channels into the video library.

Pulls video metadata via YouTube Data API v3 and captions via
youtube-transcript-api (no YouTube account needed for public videos).
Each video is stored with `hosting_type='youtube_embed'` — playback
is via YouTube iframe, which is permitted under Standard YouTube License.
No content is rehosted, so CC-BY-NC-SA content (Khan Academy, etc.) is
safe to embed.

After each video is inserted we fire Inngest event `video/ingest.requested`
which the existing Phase 3 pipeline picks up — classify via Haiku, index
transcript, align to standards, sync into video_standards join table.

Requirements (env):
    YOUTUBE_API_KEY — free tier (10K quota units/day, ~1 unit per video)

Install:
    pip install google-api-python-client youtube-transcript-api

Usage:
    docker compose exec api python scripts/ingest_youtube_catalog.py --list-channels
    docker compose exec api python scripts/ingest_youtube_catalog.py --channel khan-academy --limit 50 --dry-run
    docker compose exec api python scripts/ingest_youtube_catalog.py --channel khan-academy
    docker compose exec api python scripts/ingest_youtube_catalog.py --all --limit 200
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from uuid import uuid4

sys.path.insert(0, "/app")

from src.lms_agents.tools.db import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
log = logging.getLogger("ingest_youtube")


# ---------------------------------------------------------------------------
# Curated channel catalog
# ---------------------------------------------------------------------------
# Each entry: internal id, channel_id, display name, default_subject, license.
# channel_id is YouTube's UCxxxx identifier (find via "channel ID" on YT channel page).
#
# Standard YouTube License permits embedding; that's all we use.

CHANNELS = {
    "khan-academy": {
        "channel_id": "UC4a-Gbdw7vOaccHmFo40b9g",
        "name": "Khan Academy",
        "subject_hint": None,  # too broad; Haiku classifies per video
        "attribution": "Khan Academy",
        "license": "CC-BY-NC-SA 4.0",  # content license (we embed only, so OK)
    },
    "khan-academy-kids": {
        "channel_id": "UCw8ZhLPdQ0u_Y-TLKd61hGA",
        "name": "Khan Academy Kids",
        "subject_hint": None,
        "attribution": "Khan Academy Kids",
        "license": "CC-BY-NC-SA 4.0",
    },
    "crash-course-kids": {
        "channel_id": "UCSIvk78tK2TiviLQn4fSHaw",
        "name": "Crash Course Kids",
        "subject_hint": "Science",
        "attribution": "Crash Course Kids / PBS Digital Studios",
        "license": "CC-BY-SA 4.0",
    },
    "scishow-kids": {
        "channel_id": "UCRFVd1ndG5F-VSlmq4dpsjQ",
        "name": "SciShow Kids",
        "subject_hint": "Science",
        "attribution": "SciShow Kids",
        "license": "Standard YouTube License",
    },
    "ted-ed": {
        "channel_id": "UCsooa4yRKGN_zEE8iknghZA",
        "name": "TED-Ed",
        "subject_hint": None,
        "attribution": "TED-Ed",
        "license": "CC-BY-NC-ND 4.0",
    },
    "nasa-stem": {
        "channel_id": "UC4F1Z54E6FcHIIkhbkk-QCg",
        "name": "NASA STEM Engagement",
        "subject_hint": "Science",
        "attribution": "NASA",
        "license": "Public Domain",
    },
    "smithsonian": {
        "channel_id": "UCp1uJbMKIQirt20_BAMxkSg",
        "name": "Smithsonian Channel",
        "subject_hint": None,
        "attribution": "Smithsonian",
        "license": "Standard YouTube License",
    },
    "natgeo-kids": {
        "channel_id": "UCXVCgDuD_QCkI7gTKU7-tpg",
        "name": "National Geographic Kids",
        "subject_hint": None,
        "attribution": "National Geographic Kids",
        "license": "Standard YouTube License",
    },
}


def list_channels():
    print("Available channels:")
    for key, cfg in CHANNELS.items():
        print(f"  {key:<25} — {cfg['name']} ({cfg.get('subject_hint') or 'mixed'})")


# ---------------------------------------------------------------------------
# YouTube Data API helpers
# ---------------------------------------------------------------------------

def _get_yt_service():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY env var not set")
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def fetch_channel_videos(youtube, channel_id: str, limit: int) -> list[dict]:
    """Fetch up to `limit` recent videos from a channel via uploads playlist."""
    # Resolve uploads playlist id
    resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    items = resp.get("items") or []
    if not items:
        raise RuntimeError(f"Channel {channel_id} not found")
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    videos: list[dict] = []
    page_token = None
    while len(videos) < limit:
        page_size = min(50, limit - len(videos))
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_id,
            maxResults=page_size,
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            vid = item["contentDetails"]["videoId"]
            snip = item.get("snippet", {})
            videos.append({
                "youtube_video_id": vid,
                "title": snip.get("title") or "",
                "description": snip.get("description") or "",
                "thumbnail_url": (snip.get("thumbnails") or {}).get("medium", {}).get("url", ""),
            })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # Batch-fetch durations (contentDetails.duration → ISO 8601) 50 at a time
    for i in range(0, len(videos), 50):
        batch = videos[i:i + 50]
        resp = youtube.videos().list(
            part="contentDetails",
            id=",".join(v["youtube_video_id"] for v in batch),
        ).execute()
        dur_map = {}
        for item in resp.get("items", []):
            dur_map[item["id"]] = _parse_iso_duration(item["contentDetails"]["duration"])
        for v in batch:
            v["duration_seconds"] = dur_map.get(v["youtube_video_id"])

    return videos


def _parse_iso_duration(iso: str) -> int:
    """Parse ISO 8601 duration (PT4M13S) into seconds."""
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mn, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mn * 60 + s


def fetch_captions(youtube_video_id: str) -> str:
    """Pull English captions via youtube-transcript-api (free, no API key)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.list_transcripts(youtube_video_id)
        for t in transcript_list:
            if t.language_code.startswith("en"):
                return " ".join(seg["text"] for seg in t.fetch())
        # Fall back to any available language
        for t in transcript_list:
            return " ".join(seg["text"] for seg in t.fetch())
    except Exception as e:
        log.debug("No captions for %s: %s", youtube_video_id, e)
    return ""


# ---------------------------------------------------------------------------
# DB insert
# ---------------------------------------------------------------------------

def video_exists(cur, youtube_video_id: str) -> bool:
    cur.execute(
        "SELECT 1 FROM videos WHERE youtube_video_id = %s LIMIT 1",
        (youtube_video_id,),
    )
    return cur.fetchone() is not None


def insert_video(cur, meta: dict, channel_cfg: dict, transcript: str) -> str:
    """Insert one youtube_embed video. Returns video_id."""
    video_id = str(uuid4())
    cur.execute(
        """
        INSERT INTO videos
          (video_id, title, duration_seconds, thumbnail_url, transcript_text,
           hosting_type, youtube_video_id, source_lane, scope,
           attribution, license, source_url, subject, status)
        VALUES (%s::uuid, %s, %s, %s, %s,
                'youtube_embed', %s, 'youtube_embed', 'public',
                %s, %s, %s, %s, 'ready')
        """,
        (
            video_id,
            meta["title"][:500],
            meta.get("duration_seconds"),
            meta.get("thumbnail_url"),
            transcript,
            meta["youtube_video_id"],
            channel_cfg["attribution"],
            channel_cfg["license"],
            f"https://www.youtube.com/watch?v={meta['youtube_video_id']}",
            channel_cfg.get("subject_hint"),
        ),
    )
    return video_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def ingest_channel(channel_key: str, limit: int, dry_run: bool = False) -> dict:
    channel_cfg = CHANNELS.get(channel_key)
    if not channel_cfg:
        raise RuntimeError(f"Unknown channel: {channel_key}. See --list-channels")

    log.info("=" * 60)
    log.info("Channel: %s (limit=%d, dry_run=%s)", channel_cfg["name"], limit, dry_run)

    yt = _get_yt_service()
    videos = fetch_channel_videos(yt, channel_cfg["channel_id"], limit)
    log.info("Fetched %d video metadata records", len(videos))

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    try:
        for i, v in enumerate(videos, 1):
            if video_exists(cur, v["youtube_video_id"]):
                skipped += 1
                continue

            transcript = fetch_captions(v["youtube_video_id"])

            if dry_run:
                log.info("  [dry] %s — %s (%ds, transcript=%d chars)",
                         v["youtube_video_id"], v["title"][:60],
                         v.get("duration_seconds") or 0, len(transcript))
                inserted += 1
                continue

            video_id = insert_video(cur, v, channel_cfg, transcript)
            conn.commit()
            inserted += 1

            # Fire Inngest event for downstream processing (classify + index + align)
            # Only if the event hook is configured — otherwise we'll backfill later
            try:
                _fire_post_ingest_event(video_id)
            except Exception as e:
                log.debug("Inngest event skipped: %s", e)

            if i % 25 == 0:
                log.info("  Progress: %d/%d inserted, %d skipped", inserted, len(videos), skipped)

    finally:
        cur.close()
        conn.close()

    log.info("Channel %s complete: inserted=%d skipped=%d", channel_cfg["name"], inserted, skipped)
    return {"inserted": inserted, "skipped": skipped, "channel": channel_cfg["name"]}


def _fire_post_ingest_event(video_id: str):
    """Fire Inngest event so classify + align runs async."""
    import asyncio
    import inngest
    from src.lms_agents.inngest.client import inngest_client

    async def _send():
        await inngest_client.send(
            inngest.Event(
                name="video/ingest.requested",
                data={"video_id": video_id, "source": "youtube_catalog"},
            )
        )

    asyncio.run(_send())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-channels", action="store_true")
    ap.add_argument("--channel", type=str, help="Channel key from the curated list")
    ap.add_argument("--all", action="store_true", help="Ingest all curated channels")
    ap.add_argument("--limit", type=int, default=100, help="Max videos per channel (default 100)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.list_channels:
        list_channels()
        return

    if args.all:
        totals = {"inserted": 0, "skipped": 0, "by_channel": []}
        for key in CHANNELS:
            try:
                result = ingest_channel(key, args.limit, dry_run=args.dry_run)
                totals["inserted"] += result["inserted"]
                totals["skipped"] += result["skipped"]
                totals["by_channel"].append(result)
            except Exception as e:
                log.error("Channel %s failed: %s", key, e)
        log.info("=" * 60)
        log.info("ALL CHANNELS: inserted=%d skipped=%d", totals["inserted"], totals["skipped"])
        return

    if not args.channel:
        ap.print_help()
        sys.exit(1)

    ingest_channel(args.channel, args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
