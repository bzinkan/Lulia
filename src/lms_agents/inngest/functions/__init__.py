from src.lms_agents.inngest.functions.smoke_test import smoke_test
from src.lms_agents.inngest.functions.plan_approval import plan_approval
from src.lms_agents.inngest.functions.clip_generation import clip_generation
from src.lms_agents.inngest.functions.video_generation import video_generation
from src.lms_agents.inngest.functions.cron_stale_games import cleanup_stale_games
from src.lms_agents.inngest.functions.cron_webhooks_purge import purge_old_webhooks
from src.lms_agents.inngest.functions.cron_analytics_rollup import analytics_rollup

all_functions = [
    smoke_test,
    plan_approval,
    clip_generation,
    video_generation,
    cleanup_stale_games,
    purge_old_webhooks,
    analytics_rollup,
]
