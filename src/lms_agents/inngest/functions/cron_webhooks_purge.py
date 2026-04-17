"""Monthly purge of old processed webhook records (90-day retention)."""
import logging
import inngest
from src.lms_agents.inngest.client import inngest_client

log = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="cron-webhooks-purge",
    trigger=inngest.TriggerCron(cron="0 4 1 * *"),
)
async def purge_old_webhooks(ctx: inngest.Context, step: inngest.Step) -> dict:
    async def purge():
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM processed_webhooks WHERE processed_at < NOW() - INTERVAL '90 days'"
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        log.info(f"[Cron] Webhook purge: deleted {deleted} old events")
        return {"deleted": deleted}

    return await step.run("purge-old-events", purge)
