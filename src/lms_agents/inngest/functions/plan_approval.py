import logging
import inngest
from src.lms_agents.inngest.client import inngest_client

log = logging.getLogger(__name__)


async def _on_plan_failure(ctx: inngest.Context, step: inngest.Step) -> None:
    plan_id = ctx.event.data.get("plan_id")
    if not plan_id:
        return

    async def mark_failed():
        import os
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "db"),
            port=int(os.environ.get("DB_PORT", 5432)),
            dbname=os.environ.get("DB_NAME", "lulia"),
            user=os.environ.get("DB_USER", "lulia"),
            password=os.environ.get("DB_PASSWORD", "devpassword"),
        )
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
