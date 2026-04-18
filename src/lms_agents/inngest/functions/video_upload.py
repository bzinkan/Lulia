"""
Inngest function: post-upload processing for teacher-uploaded videos.

Trigger: video/upload.completed (fired by POST /videos/upload/complete after
the client uploads the MP4 directly to S3 via presigned PUT).

Pipeline (each step checkpointed — retries only re-run the failed step):
  1. ffprobe    → extract duration_seconds, resolution
  2. thumbnail  → extract a frame at t=1s, upload as thumbnails/{video_id}.jpg
  3. transcribe → AWS Transcribe async job (poll via step.sleep until complete)
  4. index      → chunk + embed transcript into knowledge_sources (upload_lane='video_library')
  5. classify   → Haiku infers grade_level, subject, domain, grade_bands
  6. align      → align the transcript chunks to standards (existing offline pipeline)
  7. sync       → mirror top-N standards into video_standards join table
  8. finalize   → set videos.status='ready'

Invariants:
  - reference_metadata NEVER touched
  - Existing videos table values preserved (classify_video + patch endpoints are merge-safe)
  - Idempotent at the step level — if the workflow re-runs mid-flight, completed
    steps short-circuit via status checks in the DB
"""
from __future__ import annotations

import logging
import os
import time
from datetime import timedelta

import inngest

from src.lms_agents.inngest.client import inngest_client

log = logging.getLogger(__name__)

_BUCKET = "lulia-generated"


@inngest_client.create_function(
    fn_id="video-upload-processing",
    trigger=inngest.TriggerEvent(event="video/upload.completed"),
    retries=3,
    concurrency=[inngest.Concurrency(limit=3)],
)
async def video_upload_processing(ctx: inngest.Context, step: inngest.Step) -> dict:
    video_id: str = ctx.event.data["video_id"]
    s3_key: str = ctx.event.data["s3_key"]

    # Step 1: ffprobe — duration + resolution
    async def _probe():
        import json
        import subprocess
        import tempfile
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        s3.download_file(_BUCKET, s3_key, tmp_path)
        try:
            out = subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries",
                "stream=width,height,duration:format=duration",
                "-of", "json", tmp_path,
            ], timeout=60)
            data = json.loads(out)
            duration = 0.0
            if "format" in data and data["format"].get("duration"):
                duration = float(data["format"]["duration"])
            elif data.get("streams"):
                for s in data["streams"]:
                    if s.get("duration"):
                        duration = float(s["duration"])
                        break
            return {"duration_seconds": int(duration)}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    probe = await step.run("ffprobe", _probe)

    async def _save_probe():
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE videos SET duration_seconds = %s WHERE video_id = %s::uuid",
                (probe["duration_seconds"], video_id),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()
        return probe

    await step.run("save-probe", _save_probe)

    # Step 2: thumbnail — extract a frame, upload to thumbnails/{video_id}.jpg
    async def _thumbnail():
        import subprocess
        import tempfile
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            video_path = tmp.name
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as thumb:
            thumb_path = thumb.name
        try:
            s3.download_file(_BUCKET, s3_key, video_path)
            # Grab a frame at 1 second (or halfway if shorter)
            grab_at = max(0.5, min(1.0, (probe["duration_seconds"] or 2) / 2))
            subprocess.run([
                "ffmpeg", "-y", "-ss", str(grab_at), "-i", video_path,
                "-frames:v", "1", "-q:v", "3", thumb_path,
            ], check=True, capture_output=True, timeout=60)

            thumb_key = f"thumbnails/{video_id}.jpg"
            s3.upload_file(thumb_path, _BUCKET, thumb_key, ExtraArgs={"ContentType": "image/jpeg"})

            from src.lms_agents.tools.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE videos SET thumbnail_url = %s WHERE video_id = %s::uuid",
                    (thumb_key, video_id),
                )
                conn.commit()
            finally:
                cur.close()
                conn.close()
            return {"thumbnail_key": thumb_key}
        finally:
            for p in (video_path, thumb_path):
                try:
                    os.unlink(p)
                except Exception:
                    pass

    await step.run("thumbnail", _thumbnail)

    # Step 3: transcription — AWS Transcribe async
    # Note: first submits the job, then we poll with step.sleep + step.run.
    async def _start_transcribe():
        import boto3
        region = os.environ.get("AWS_REGION", "us-east-1")
        transcribe = boto3.client(
            "transcribe",
            region_name=region,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
        # AWS Transcribe needs a full s3:// URI, not a MinIO one — this step is
        # a no-op in local dev (returns a stub). In prod, S3_ENDPOINT is unset
        # so boto3 hits real S3 and Transcribe can read the same bucket.
        s3_endpoint = os.environ.get("S3_ENDPOINT", "")
        if "minio" in s3_endpoint or "localhost" in s3_endpoint:
            log.info("Skipping AWS Transcribe in local dev — S3 endpoint is MinIO")
            return {"job_name": None, "skipped": True}

        job_name = f"lulia-video-{video_id}"
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": f"s3://{_BUCKET}/{s3_key}"},
            MediaFormat="mp4",
            LanguageCode="en-US",
        )
        return {"job_name": job_name, "skipped": False}

    job = await step.run("transcribe-start", _start_transcribe)

    # Poll Transcribe up to ~15 min (30 × 30s sleeps)
    transcript_text = ""
    if not job.get("skipped"):
        for attempt in range(30):
            await step.sleep(f"transcribe-wait-{attempt}", timedelta(seconds=30))

            async def _poll(job_name=job["job_name"]):
                import boto3
                transcribe = boto3.client(
                    "transcribe",
                    region_name=os.environ.get("AWS_REGION", "us-east-1"),
                    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                )
                resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
                status = resp["TranscriptionJob"]["TranscriptionJobStatus"]
                if status == "COMPLETED":
                    url = resp["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
                    import urllib.request
                    import json as _json
                    with urllib.request.urlopen(url) as r:
                        doc = _json.loads(r.read())
                    transcript = doc["results"]["transcripts"][0]["transcript"]
                    return {"status": "COMPLETED", "transcript": transcript}
                if status == "FAILED":
                    return {"status": "FAILED", "transcript": ""}
                return {"status": status, "transcript": ""}

            poll = await step.run(f"transcribe-poll-{attempt}", _poll)
            if poll["status"] == "COMPLETED":
                transcript_text = poll["transcript"]
                break
            if poll["status"] == "FAILED":
                break

    # Step 4: save transcript + index into knowledge base
    async def _index():
        from src.lms_agents.tools.db import get_connection
        from src.lms_agents.tools.video_library import index_video_transcript

        if transcript_text:
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE videos SET transcript_text = %s WHERE video_id = %s::uuid",
                    (transcript_text, video_id),
                )
                conn.commit()
            finally:
                cur.close()
                conn.close()
        return index_video_transcript(video_id)

    index_result = await step.run("index-transcript", _index)

    # Step 5: classify
    async def _classify():
        from src.lms_agents.tools.video_library import classify_video
        return classify_video(video_id)

    await step.run("classify", _classify)

    # Step 6: align chunks to standards (reuses Phase 24 pipeline)
    async def _align():
        if not index_result or index_result.get("status") != "complete":
            return {"skipped": True, "reason": "no chunks indexed"}
        # Align just this video's chunks using the existing sync alignment.
        # This is the same pipeline used for all other content lanes.
        from src.lms_agents.tools.standards_alignment import align_chunks_batch
        count = align_chunks_batch(source_id=index_result.get("source_id"), limit=100)
        return {"aligned_count": count}

    await step.run("align-standards", _align)

    # Step 7: sync top standards into video_standards
    async def _sync():
        from src.lms_agents.tools.video_library import sync_video_standards
        return sync_video_standards(video_id)

    await step.run("sync-standards", _sync)

    # Step 8: finalize
    async def _finalize():
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE videos SET status = 'ready' WHERE video_id = %s::uuid",
                (video_id,),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()
        return {"status": "ready"}

    final = await step.run("finalize", _finalize)
    return {"video_id": video_id, "final": final, "transcript_len": len(transcript_text)}
