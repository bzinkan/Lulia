"""
Inngest function: Video generation (Script Agent + TTS + render + persist).

The video_crew.generate_video() function handles the full pipeline including
DB persistence, so this wrapper just runs it as a retryable step.
"""
import logging
import inngest
from src.lms_agents.inngest.client import inngest_client

log = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="video-generation",
    trigger=inngest.TriggerEvent(event="video/generation.requested"),
    retries=1,
    concurrency=[inngest.Concurrency(limit=5)],
)
async def video_generation(ctx: inngest.Context, step: inngest.Step) -> dict:
    data = ctx.event.data

    async def generate():
        from src.lms_agents.crews.video_crew import generate_video
        return generate_video(
            assignment_id=data["assignment_id"],
            teacher_id=data["teacher_id"],
            voice_id=data.get("voice_id"),
            use_my_voice=data.get("use_my_voice", False),
            target_duration=data.get("target_duration", 240),
            theme=data.get("theme", "modern_clean"),
        )

    result = await step.run("generate-video", generate)
    return result
