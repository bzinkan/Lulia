"""Nightly cleanup of stale game sessions from Redis."""
import json
import logging
import inngest
from src.lms_agents.inngest.client import inngest_client

log = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="cron-stale-games-cleanup",
    trigger=inngest.TriggerCron(cron="0 2 * * *"),
)
async def cleanup_stale_games(ctx: inngest.Context, step: inngest.Step) -> dict:
    async def scan_and_delete():
        from src.lms_agents.tools.redis_client import get_redis
        r = get_redis()
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = r.scan(cursor, match="game:*", count=100)
            for key in keys:
                if ":" in key and key.count(":") > 1:
                    continue
                ttl = r.ttl(key)
                if ttl == -1:
                    raw = r.get(key)
                    if not raw:
                        r.delete(key)
                        deleted += 1
                        continue
                    try:
                        state = json.loads(raw)
                    except (ValueError, TypeError):
                        r.delete(key)
                        deleted += 1
                        continue
                    if state.get("status") in ("finished", None):
                        r.delete(key)
                        deleted += 1
            if cursor == 0:
                break
        log.info(f"[Cron] Stale game cleanup: deleted {deleted} keys")
        return {"deleted": deleted}

    return await step.run("scan-delete", scan_and_delete)
