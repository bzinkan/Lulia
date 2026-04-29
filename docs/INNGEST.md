# Inngest — Operational Guide

## Architecture

```
Teacher action (HTTP)
  → FastAPI route charges credits / validates / fires inngest event
  → Inngest server matches event to function
  → Inngest calls POST /api/inngest on the API container
  → Each step is checkpointed; failures retry only the failed step
  → Dashboard at :8288 shows execution history + traces
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| `api` | 8000 | FastAPI app + Inngest serve endpoint (`/api/inngest`) |
| `inngest` | 8288 | Inngest dev server (local) or self-hosted server (prod) |

## Functions

| fn_id | Trigger | Retries | Concurrency | Purpose |
|-------|---------|---------|-------------|---------|
| `smoke-test` | `test/smoke.requested` | 3 | — | Verify stack works |
| `plan-approval` | `plan/approval.requested` | 2 | — | Lesson plan material generation |
| `clip-generation` | `clip/generation.requested` | 2 | 3 (Vertex) | Retained Veo short-clip path; launch usage undecided |
| `video-generation` | `video/generation.requested` | 1 | 5 (Sonnet) | Retained generated-video pipeline/fallback |
| `cron-stale-games-cleanup` | Daily 2am UTC | 3 | — | Purge orphaned Redis game keys |
| `cron-webhooks-purge` | 1st of month 4am UTC | 3 | — | Clean 90-day-old webhook dedup records |
| `cron-analytics-rollup` | Weekly Sunday 3am UTC | 3 | — | Credit + game usage aggregation |

## Adding a New Function

1. Create `src/lms_agents/inngest/functions/my_function.py`
2. Use `async def` helpers for `step.run` (never bare lambdas)
3. Import + add to `all_functions` in `src/lms_agents/inngest/functions/__init__.py`
4. Restart the API — Inngest auto-discovers new functions

## Credit Atomicity Pattern

```python
# Charge at the HTTP endpoint (instant teacher feedback)
charge = charge_credits(teacher_id, cost, ...)
if not charge["success"]:
    return 402

# Fire event with credits_charged in data
await inngest_client.send(Event(
    name="feature/generate.requested",
    data={..., "credits_charged": cost},
))

# In on_failure handler: refund
grant_credits(teacher_id, credits_charged, bucket="purchased")
```

## WebSocket Bridge Pattern

Inngest functions cannot hold WebSocket connections. To notify game clients:

```python
# Inside an Inngest function step
from src.lms_agents.tools.redis_client import get_redis
r = get_redis()
r.publish(f"game:{pin}:events", json.dumps({"type": "event_name", ...}))
```

The existing `game_server.py` pub/sub listener picks this up and broadcasts
to connected WebSocket clients. No changes to game_server.py needed.

## Local Development

```bash
docker compose up -d api inngest
# Dashboard: http://localhost:8288
# Send test event:
curl -X POST http://localhost:8288/e/ \
  -H 'Content-Type: application/json' \
  -d '{"name": "test/smoke.requested", "data": {}}'
```

## Production (ECS Self-Hosted)

- Task definition: `infra/inngest-task-definition.json`
- Requires: `INNGEST_SIGNING_KEY`, `INNGEST_EVENT_KEY`, `INNGEST_REDIS_URI`
- Do NOT set `INNGEST_DEV` in production
- Port 8288 is internal only — access dashboard via SSH tunnel
- Cost: ~$8/month (256 CPU / 512 MB Fargate task)

### Signing Key Rotation

1. Generate new key pair
2. Set new `INNGEST_SIGNING_KEY` on both API and Inngest ECS tasks
3. Deploy both simultaneously (rolling update)
4. Old key is invalidated immediately — no grace period
