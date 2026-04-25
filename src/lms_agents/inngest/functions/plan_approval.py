import logging
import inngest
from src.lms_agents.inngest.client import inngest_client

log = logging.getLogger(__name__)


async def _on_plan_failure(ctx: inngest.Context, step: inngest.Step) -> None:
    plan_id = ctx.event.data.get("plan_id")
    if not plan_id:
        return

    async def mark_failed():
        # Pooled connection — Inngest workers share the API's pool when
        # running in-process, or get their own pool when running as the
        # standalone worker service. Either way, `.close()` releases.
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE lesson_plans SET status = 'failed' WHERE plan_id = %s",
            (plan_id,),
        )
        conn.commit()
        cur.close()
        conn.close()

    await step.run("mark-failed", mark_failed)
    log.error(f"[Inngest] Plan approval permanently failed: plan_id={plan_id}")


@inngest_client.create_function(
    fn_id="plan-approval",
    trigger=inngest.TriggerEvent(event="plan/approval.requested"),
    retries=2,
    on_failure=_on_plan_failure,
)
async def plan_approval(ctx: inngest.Context, step: inngest.Step) -> dict:
    plan_id = ctx.event.data["plan_id"]
    sync_to_classroom = ctx.event.data.get("sync_to_classroom", False)

    async def run_generation():
        from src.lms_agents.crews.planning_crew import approve_plan
        approve_plan(plan_id, sync_to_classroom=sync_to_classroom)

    await step.run("generate-materials", run_generation)
    return {"plan_id": plan_id, "status": "complete"}
