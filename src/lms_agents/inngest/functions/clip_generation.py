"""
Inngest function: Short Clip generation via Veo 3 Fast.

Runs the Veo polling loop as a retryable step. Credits are charged by the
endpoint BEFORE the event fires (instant teacher feedback). This function
handles generation + persistence + refund-on-failure.
"""
import logging
import inngest
from src.lms_agents.inngest.client import inngest_client

log = logging.getLogger(__name__)


async def _on_clip_failure(ctx: inngest.Context, step: inngest.Step) -> None:
    data = ctx.event.data
    clip_id = data.get("clip_id")
    teacher_id = data.get("teacher_id")
    credits_charged = data.get("credits_charged", 0)

    if teacher_id and credits_charged > 0:
        async def refund():
            from src.lms_agents.tools.credit_manager import grant_credits
            grant_credits(
                teacher_id, credits_charged,
                reason=f"Refund: Veo generation permanently failed for clip {clip_id}",
                bucket="purchased",
            )
        await step.run("refund-credits", refund)

    if clip_id:
        async def mark_failed():
            from src.lms_agents.tools.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE short_clips SET status = 'failed' WHERE clip_id = %s",
                (clip_id,),
            )
            conn.commit()
            cur.close()
            conn.close()
        await step.run("mark-clip-failed", mark_failed)

    log.error(f"[Inngest] Clip generation permanently failed: clip_id={clip_id}")


@inngest_client.create_function(
    fn_id="clip-generation",
    trigger=inngest.TriggerEvent(event="clip/generation.requested"),
    retries=2,
    concurrency=[inngest.Concurrency(limit=3)],
    on_failure=_on_clip_failure,
)
async def clip_generation(ctx: inngest.Context, step: inngest.Step) -> dict:
    data = ctx.event.data
    clip_id = data["clip_id"]

    async def call_veo():
        from src.lms_agents.tools.veo_generator import generate_clip
        return generate_clip(
            prompt=data["prompt"],
            duration_sec=data["duration_sec"],
            aspect_ratio=data.get("aspect_ratio", "16:9"),
            reference_image_uri=data.get("reference_image_uri"),
        )

    result = await step.run("generate-clip", call_veo)

    if not result.get("success"):
        raise inngest.NonRetriableError(
            f"Veo returned failure: {result.get('error', 'unknown')}"
        )

    async def persist():
        from src.lms_agents.tools.db import get_connection
        from psycopg2.extras import Json
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """UPDATE short_clips
               SET status = 'complete',
                   video_uris = %s, primary_uri = %s,
                   segments = %s, model = %s,
                   duration_sec = %s
               WHERE clip_id = %s""",
            (
                result["video_uris"], result["primary_uri"],
                result.get("segments", 1), result.get("model"),
                result.get("duration_sec", data["duration_sec"]),
                clip_id,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()

    await step.run("persist-clip", persist)
    return {"clip_id": clip_id, "status": "complete"}
