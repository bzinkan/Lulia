import inngest
from src.lms_agents.inngest.client import inngest_client


@inngest_client.create_function(
    fn_id="smoke-test",
    trigger=inngest.TriggerEvent(event="test/smoke.requested"),
)
async def smoke_test(ctx: inngest.Context, step: inngest.Step) -> dict:
    async def echo_hello():
        return "Inngest is alive — Lulia LMS"

    result = await step.run("echo", echo_hello)
    return {"ok": True, "message": result}
