"""Weekly analytics rollup — aggregates credit usage + game results."""
import logging
import inngest
from src.lms_agents.inngest.client import inngest_client

log = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="cron-analytics-rollup",
    trigger=inngest.TriggerCron(cron="0 3 * * 0"),
)
async def analytics_rollup(ctx: inngest.Context, step: inngest.Step) -> dict:
    async def aggregate():
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        cur = conn.cursor()

        # Credit usage summary for the past week
        cur.execute("""
            SELECT type, COUNT(*) as count, SUM(ABS(amount)) as total_credits
            FROM credit_transactions_v2
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY type
        """)
        credit_rows = cur.fetchall()
        credit_summary = {r[0]: {"count": r[1], "credits": r[2]} for r in credit_rows}

        # Game sessions summary
        cur.execute("""
            SELECT COUNT(*) as games, COALESCE(SUM(total_players), 0) as players
            FROM game_results
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """)
        game_row = cur.fetchone()
        game_summary = {"games": game_row[0], "players": game_row[1]} if game_row else {}

        cur.close()
        conn.close()
        log.info(f"[Cron] Weekly rollup: {credit_summary}, games: {game_summary}")
        return {"credits": credit_summary, "games": game_summary}

    return await step.run("aggregate-weekly", aggregate)
