# Inngest Implementation Plan — Lulia LMS

> Merged from the original v1.0 plan + two independent code audits.
> April 2026 | Tailored to the actual codebase at `src/lms_agents/`.

---

## 1. Why Inngest

Lulia's backend is FastAPI + Redis (game state) + Postgres (persistence). AI content
generation (Claude Haiku, Gemini 2.5 Flash, Vertex AI Veo 3, Imagen 3, Polly,
ElevenLabs) runs as **inline sync calls** or **daemon threads**. This creates:

| Gap | Impact | Where |
|-----|--------|-------|
| No step-level retries | Transient Veo 500 → re-run Claude ($0.01–$0.10 wasted) | `clips.py`, `question_generator.py` |
| Daemon threads | Unobservable, unkillable, no retry | `routers/plans.py:130` |
| No concurrency controls | 20 teachers → 20 parallel Claude calls → rate limit | `question_generator.py` |
| No scheduler | Stale Redis game sessions accumulate forever | No cron exists |
| No webhook idempotency | Stripe retries → duplicate credit grants | `routers/stripe_webhooks.py` |
| No observability | Background failures require log-diving | Worker stub is empty |

Inngest replaces all of this with step-function workflows, automatic retries,
declarative concurrency, cron triggers, and a built-in dashboard.

---

## 2. Architecture

### 2.1 How It Fits

```
Teacher clicks "Approve Plan"
  → FastAPI sends event: plan/approve.requested
  → Inngest server matches event → calls /api/inngest on the api container
  → Each step is checkpointed; failures retry only the failed step
  → Dashboard at :8288 shows execution history + traces
```

Your existing routes, WebSocket handlers (`game_server.py`), and game logic are
**untouched**. The only new endpoint is `/api/inngest` mounted via the SDK.

### 2.2 Docker Compose

Add one service after `redis` in `docker-compose.yml`:

```yaml
  inngest:
    image: inngest/inngest:latest
    command: "inngest dev -u http://api:8000/api/inngest"
    ports:
      - "8288:8288"    # Dev dashboard + event API
    depends_on:
      - api
```

> **Fix from original plan:** service name is `api`, not `app`.

Add env vars to the `api` service:

```yaml
    environment:
      - INNGEST_DEV=1
      - INNGEST_BASE_URL=http://inngest:8288
```

### 2.3 Dependency

Add to `requirements.txt`:

```
inngest>=2.0
```

---

## 3. Scaffolding (Phase 1)

### 3.1 Client Singleton

Create `src/lms_agents/inngest_client.py`:

```python
import logging
import inngest

inngest_client = inngest.Inngest(
    app_id="lulia",
    logger=logging.getLogger("uvicorn"),
)
```

### 3.2 Mount in FastAPI

In `src/lms_agents/main.py`, after all `app.include_router(...)` calls (after line 105):

```python
import inngest.fast_api
from src.lms_agents.inngest_client import inngest_client
from src.lms_agents.workflows import ALL_FUNCTIONS

inngest.fast_api.serve(
    app,
    inngest_client,
    ALL_FUNCTIONS,
)
```

### 3.3 Workflow Registry

Create `src/lms_agents/workflows/__init__.py`:

```python
from src.lms_agents.workflows.plan_approval import approve_plan_workflow
# Add more as phases ship

ALL_FUNCTIONS = [
    approve_plan_workflow,
]
```

### 3.4 Smoke Test

Create `src/lms_agents/workflows/smoke_test.py`:

```python
import inngest
from src.lms_agents.inngest_client import inngest_client


@inngest_client.create_function(
    fn_id="smoke-test",
    trigger=inngest.TriggerEvent(event="test/smoke"),
)
async def smoke_test(ctx: inngest.Context, step: inngest.Step):
    result = await step.run("echo", async_echo, "Inngest is alive")
    return {"ok": True, "echo": result}


async def async_echo(msg: str) -> str:
    return msg
```

> **Fix from original plan:** use `async def` helper functions, not bare lambdas.
> `ctx.step.run("name", lambda: some_async_fn())` silently fails because the
> lambda returns a coroutine without awaiting it.

Verify: `docker compose up`, open `http://localhost:8288`, send a test event,
confirm execution + step trace visible in the dashboard.

---

## 4. Phase 2 — Plan Approval (Kill the Daemon Thread)

**This is the actual production bug.** `routers/plans.py` line 130 launches a
`threading.Thread(daemon=True)` that calls `approve_plan()`. It's unobservable,
has no retry, and silently drops errors.

### 4.1 The Workflow

Create `src/lms_agents/workflows/plan_approval.py`:

```python
import logging
import inngest
from src.lms_agents.inngest_client import inngest_client

log = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="plan-approval",
    trigger=inngest.TriggerEvent(event="plan/approve.requested"),
    retries=2,
)
async def approve_plan_workflow(ctx: inngest.Context, step: inngest.Step):
    plan_id = ctx.event.data["plan_id"]
    sync_to_classroom = ctx.event.data.get("sync_to_classroom", False)

    # Step 1: Mark plan as generating
    await step.run("mark-generating", _mark_generating, plan_id)

    # Step 2: Run the heavy generation (Claude + Gemini + persist)
    await step.run("generate", _generate, plan_id, sync_to_classroom)

    return {"plan_id": plan_id, "status": "complete"}


async def _mark_generating(plan_id: str):
    from src.lms_agents.tools.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE lesson_plans SET status = 'generating', approved_at = NOW() "
        "WHERE plan_id = %s",
        (plan_id,),
    )
    conn.commit()
    cur.close()
    conn.close()


async def _generate(plan_id: str, sync_to_classroom: bool):
    from src.lms_agents.crews.planning_crew import approve_plan
    try:
        approve_plan(plan_id, sync_to_classroom=sync_to_classroom)
    except Exception as e:
        # Mark as failed so the teacher sees it, then re-raise for Inngest retry
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
        raise  # Inngest will retry this step
```

### 4.2 Update the Router

In `src/lms_agents/routers/plans.py`, replace the `threading.Thread` block:

```python
# BEFORE (daemon thread — remove this):
#   thread = threading.Thread(target=_run, daemon=True)
#   thread.start()

# AFTER (event-driven):
from src.lms_agents.inngest_client import inngest_client
import inngest

@router.put("/{plan_id}/approve")
async def approve(plan_id: UUID, req: ApproveRequest = ApproveRequest()):
    plan_id_str = str(plan_id)

    await inngest_client.send(
        inngest.Event(
            name="plan/approve.requested",
            data={
                "plan_id": plan_id_str,
                "sync_to_classroom": req.sync_to_classroom,
            },
        )
    )

    return {"plan_id": plan_id_str, "status": "generating"}
```

The route now returns immediately. The status update (`generating` → `complete`
or `failed`) is handled by the workflow. The teacher's frontend already polls
for plan status — no change needed there.

---

## 5. Phase 3 — Stripe Webhook Idempotency

**5-line fix that prevents real double-charging.** Stripe retries webhooks on
timeout or 5xx. Today `stripe_webhooks.py` processes every delivery, no dedup.

### 5.1 Migration

Create `scripts/migrations/migrate_023_webhook_idempotency.py`:

```sql
CREATE TABLE IF NOT EXISTS processed_webhooks (
    event_id   TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_pw_processed_at ON processed_webhooks (processed_at);
```

### 5.2 Guard in the Handler

In `src/lms_agents/routers/stripe_webhooks.py`, after signature verification:

```python
event_id = event.get("id")
if not event_id:
    return {"received": True}

# Idempotency check
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT 1 FROM processed_webhooks WHERE event_id = %s", (event_id,))
if cur.fetchone():
    cur.close(); conn.close()
    return {"received": True}  # Already processed

# Mark as processing (insert first, process second — crash-safe)
cur.execute(
    "INSERT INTO processed_webhooks (event_id, event_type) VALUES (%s, %s) "
    "ON CONFLICT DO NOTHING",
    (event_id, event_type),
)
conn.commit()
cur.close(); conn.close()
```

### 5.3 Cleanup Cron (ships with Phase 5)

```python
@inngest_client.create_function(
    fn_id="cleanup-processed-webhooks",
    trigger=inngest.TriggerCron(cron="0 4 * * *"),
)
async def cleanup_webhooks(ctx: inngest.Context, step: inngest.Step):
    await step.run("purge-old", _purge_old_webhooks)

async def _purge_old_webhooks():
    from src.lms_agents.tools.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM processed_webhooks WHERE processed_at < NOW() - INTERVAL '30 days'"
    )
    conn.commit()
    cur.close(); conn.close()
```

---

## 6. Phase 4 — Video + Assignment Generation

Move Veo clip generation and Haiku question generation off the request thread.

### 6.1 Clips (Veo 3 Fast)

```python
@inngest_client.create_function(
    fn_id="generate-clip",
    trigger=inngest.TriggerEvent(event="clip/generate.requested"),
    retries=2,
    concurrency=[inngest.Concurrency(limit=3)],  # Vertex AI quota
)
async def generate_clip_workflow(ctx: inngest.Context, step: inngest.Step):
    data = ctx.event.data
    teacher_id = data["teacher_id"]
    clip_id = data["clip_id"]
    duration_sec = data["duration_sec"]

    # Step 1: Charge credits (idempotent — clip_id is unique)
    charge = await step.run("charge-credits", _charge_clip,
                            teacher_id, duration_sec, clip_id)
    if not charge["success"]:
        return {"error": charge["error"]}

    # Step 2: Call Veo (retryable — if this fails, step 1 is memoized)
    result = await step.run("call-veo", _call_veo,
                            data["prompt"], duration_sec,
                            data["aspect_ratio"], data.get("reference_image_uri"))

    if not result["success"]:
        # Step 3a: Refund on permanent failure
        await step.run("refund", _refund_clip, teacher_id, duration_sec, clip_id)
        return {"error": result["error"]}

    # Step 3b: Persist
    await step.run("persist", _persist_clip, clip_id, data, result)

    return {"clip_id": clip_id, "video_uris": result["video_uris"]}
```

**Credit atomicity preserved:** charge is step 0 (memoized), so retries of step 1
(Veo) never double-charge. Refund is a separate step that runs only on Veo failure.

### 6.2 Haiku Question Generation

```python
@inngest_client.create_function(
    fn_id="generate-questions-throttled",
    trigger=inngest.TriggerEvent(event="ai/questions.requested"),
    concurrency=[inngest.Concurrency(limit=5)],
    throttle=inngest.Throttle(limit=30, period="1m"),
    retries=3,
)
async def generate_questions_workflow(ctx: inngest.Context, step: inngest.Step):
    data = ctx.event.data

    # Step 1: Charge credits
    charge = await step.run("charge", _charge_questions,
                            data["teacher_id"], data["cost"],
                            data["reference_type"])
    if not charge["success"]:
        return {"error": charge["error"]}

    # Step 2: Call Haiku (retryable)
    questions = await step.run("call-haiku", _call_haiku,
                               data["topic"], data["grade"],
                               data["subject"], data["count"],
                               data.get("standard_codes"))

    if not questions["success"]:
        await step.run("refund", _refund_questions,
                       data["teacher_id"], data["cost"])
        return {"error": questions["error"]}

    return questions
```

Throttle caps Claude at 5 concurrent + 30/minute. Excess requests queue
automatically — no custom rate-limiter code.

---

## 7. Phase 5 — Scheduled Jobs

### 7.1 Stale Game Session Cleanup

```python
@inngest_client.create_function(
    fn_id="cleanup-expired-sessions",
    trigger=inngest.TriggerCron(cron="0 3 * * *"),
)
async def cleanup_sessions(ctx: inngest.Context, step: inngest.Step):
    count = await step.run("purge-redis", _purge_expired_game_sessions)
    await step.run("archive-postgres", _archive_old_session_data)
    return {"purged": count}
```

### 7.2 Weekly Analytics Rollup

```python
@inngest_client.create_function(
    fn_id="weekly-analytics",
    trigger=inngest.TriggerCron(cron="TZ=America/New_York 0 9 * * MON"),
)
async def weekly_analytics(ctx: inngest.Context, step: inngest.Step):
    stats = await step.run("aggregate", _compute_weekly_stats)
    await step.run("store", _save_analytics, stats)
```

### 7.3 Replace the Worker Stub

The existing `src/lms_agents/worker/scheduler.py` is a `while True: sleep(10)`
loop. **Delete it.** The Inngest container replaces it entirely.

---

## 8. Phase 6 — Production Deployment (AWS)

### 8.1 Self-Hosted on ECS (Recommended)

Lulia already runs RDS Postgres + ElastiCache Redis. Self-hosting Inngest is free
(Apache 2.0), unlimited runs, and uses the existing infra:

```yaml
# ECS Task Definition — Inngest sidecar
image: inngest/inngest:latest
cpu: 256
memory: 512
environment:
  INNGEST_EVENT_KEY: <your-hex-key>
  INNGEST_SIGNING_KEY: <your-signing-key>
  INNGEST_POSTGRES_URI: postgres://inngest:pass@your-rds:5432/inngest_db
  INNGEST_REDIS_URI: redis://your-elasticache:6379
```

Create a separate `inngest_db` database on the existing RDS instance.

API task definition changes:

```yaml
environment:
  INNGEST_EVENT_KEY: <same-hex-key>
  INNGEST_SIGNING_KEY: <same-signing-key>
  # Do NOT set INNGEST_DEV in production
```

Ensure `/api/inngest` is reachable from the Inngest container (same VPC,
security group allows internal traffic on port 8000).

### 8.2 Inngest Cloud (Alternative)

Free tier: 50K function runs/month. For beta scale (~8K runs/month), this works.
No extra container. Set `INNGEST_EVENT_KEY` + `INNGEST_SIGNING_KEY` on the API
task; Inngest Cloud pushes work to your `/api/inngest` endpoint over HTTPS.

---

## 9. WebSocket + Inngest Pattern

Inngest functions **cannot** push to live WebSocket connections directly. For
features that need to notify connected clients (e.g., future game-end reports):

```
Inngest step.run("broadcast", publish_to_redis, channel, payload)
  → Redis pub/sub channel "game:{pin}:events"
  → game_server.py subscriber relays to connected WebSocket clients
```

This uses the existing pub/sub infrastructure in `game_server.py`. No new
infrastructure needed — just publish to the right Redis channel from the
Inngest function.

---

## 10. Event Naming Convention

Standardize all events as `<domain>/<entity>.<state>`:

| Event | Triggered By | Handler |
|-------|-------------|---------|
| `plan/approve.requested` | `PUT /plans/{id}/approve` | `approve_plan_workflow` |
| `clip/generate.requested` | `POST /clips/generate` | `generate_clip_workflow` |
| `ai/questions.requested` | Game setup (custom/standards) | `generate_questions_workflow` |
| `game/session.ended` | `end_game()` (future) | Fan-out (future) |
| `teacher/signup.completed` | Auth flow (future) | Onboarding drip (post-beta) |
| `test/smoke` | Manual / CI | Smoke test |

---

## 11. Phased Rollout Summary

| Phase | What | Why | Effort |
|-------|------|-----|--------|
| 1 | Scaffold + smoke test | Prove the stack works | 2 hrs |
| 2 | Plan approval (kill daemon thread) | **Actual production bug** — unobservable background work | 3 hrs |
| 3 | Stripe webhook idempotency | Prevents real double-charging on retries | 1 hr |
| 4 | Video + question generation | UX + reliability; step-level retry saves LLM cost | 4 hrs |
| 5 | Scheduled jobs (cleanup, analytics) | Nice-to-have, not urgent | 2 hrs |
| 6 | Production deployment (ECS self-host) | Final step | 3 hrs |
| — | Teacher onboarding drip | Post-beta, as original plan says | — |
| — | Game-end fan-out (reports, notifications) | Only after notifications feature ships | — |

---

## 12. Cost Analysis

**Self-hosted (recommended):** Free. Apache 2.0 license, unlimited runs.
Container overhead: 256MB RAM, 0.25 vCPU (~$8/month on Fargate).

**Cloud free tier:** 50K runs/month. Estimated usage at beta:
- Plans: ~300 approvals/month = 300 runs
- Clips: ~200 clips/month = 200 runs (× 3 steps = 600 step executions, but
  billed as 200 "runs")
- Questions: ~500 game setups/month = 500 runs
- Crons: ~60 runs/month
- **Total: ~1,060 runs/month** — well within free tier

> A "function run" = one complete execution of a function, regardless of step
> count. The original plan overcounted at 8,500.

---

## 13. Checklist Before Executing

- [ ] Add `inngest>=2.0` to `requirements.txt`
- [ ] Fix docker-compose service name: `api`, not `app`
- [ ] Use `async def` helpers for `step.run()`, never bare lambdas wrapping async code
- [ ] Preserve credit charge-before pattern (charge in step 0, refund in catch step)
- [ ] Add `on_failure` handler for Sentry alerting on every workflow
- [ ] Delete `src/lms_agents/worker/scheduler.py` after Phase 5 ships
- [ ] Document Redis pub/sub bridge pattern for future WS-facing workflows
