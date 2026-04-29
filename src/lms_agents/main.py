"""
Lulia — AI-Powered Learning Management System
FastAPI Application Entry Point
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.lms_agents.tools.observability import (
    RequestIdMiddleware,
    configure_logging,
    register_exception_handlers,
)
from src.lms_agents.tools.rate_limit import limiter, RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

# Configure structured logging BEFORE creating the FastAPI app so imports that
# grab a logger immediately get the right formatter.
configure_logging()
log = logging.getLogger(__name__)

app = FastAPI(
    title="Lulia API",
    description="AI-Powered LMS — 16 agents, 20+ templates, interactive activities, live games",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
async def run_pending_migrations():
    """Auto-apply DB migrations on API boot.

    Two stages, in order:
      1. Legacy idempotent `scripts/migrate_*.py` chain, tracked in the
         `schema_migrations` table. This is what's been running for phases
         17-28; we keep it so no one has to hand-translate 14 scripts.
      2. Alembic — stamps the baseline if the DB has never seen Alembic,
         then runs `upgrade head` to apply any NEW migrations authored
         after today. Alembic is the forward path; migrate_*.py is frozen.

    Controlled by AUTO_MIGRATE env var (default on).
    Set FAIL_ON_MIGRATION_ERROR=true in prod to hard-fail on bad migrations.
    """
    if os.environ.get("AUTO_MIGRATE", "true").lower() != "true":
        log.info("[boot] AUTO_MIGRATE disabled, skipping migrations")
        return
    hard_fail = os.environ.get("FAIL_ON_MIGRATION_ERROR", "false").lower() == "true"

    # --- Stage 1: legacy chain --------------------------------------------
    try:
        from scripts.run_migrations import run_pending
        result = run_pending()
        log.info(
            f"[boot] migrations: {len(result['ran'])} applied, "
            f"{len(result['skipped'])} already-applied, "
            f"{len(result['failed'])} failed"
        )
        if result["failed"] and hard_fail:
            raise RuntimeError(f"Migration failures: {[n for n,_ in result['failed']]}")
    except Exception as e:
        log.error(f"[boot] migration runner error: {e}")
        if hard_fail:
            raise

    # --- Stage 2: Alembic stamp + upgrade ---------------------------------
    # The stamp is a no-op on every boot after the first (it checks for an
    # existing alembic_version row). The upgrade is a no-op once we're at
    # HEAD. Both are cheap enough to run unconditionally on warm starts.
    try:
        from scripts.alembic_stamp_baseline import stamp_baseline_if_needed
        stamp_result = stamp_baseline_if_needed()
        log.info(f"[boot] alembic baseline: {stamp_result}")

        import subprocess, sys
        from pathlib import Path
        project_root = str(Path(__file__).resolve().parents[2])
        upgrade = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=project_root, capture_output=True, text=True, timeout=120,
        )
        if upgrade.returncode == 0:
            log.info("[boot] alembic upgrade head: ok")
        else:
            err = (upgrade.stderr or upgrade.stdout).strip()[:500]
            log.error(f"[boot] alembic upgrade failed: {err}")
            if hard_fail:
                raise RuntimeError(f"Alembic upgrade failed: {err}")
    except Exception as e:
        log.error(f"[boot] alembic runner error: {e}")
        if hard_fail:
            raise

# Request-ID middleware (added before CORS so every request — even rejected
# CORS preflights — gets a correlation ID in the response headers).
app.add_middleware(RequestIdMiddleware)

# CORS for dashboard. Origins are read from CORS_ORIGINS (comma-separated) so
# each environment (local, staging, prod) can configure its own allowlist
# without a code change.
_cors_default = "http://localhost:3000,http://localhost:3001"
_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", _cors_default).split(",")
    if o.strip()
]
log.info("cors_origins_configured", extra={"origins": _cors_origins})
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)

# Install the global exception handler so uncaught errors return a safe JSON
# body with the request_id for support triage, rather than a stack trace.
register_exception_handlers(app)

# Rate limiter. `app.state.limiter` is the convention slowapi's decorator
# looks up at request time, so routers can do `@limiter.limit("10/minute")`
# without importing `app` and creating a cycle.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health")
async def health_check():
    """Liveness probe: fast, no external deps."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/ready")
async def readiness_check():
    """Readiness probe: verifies the app can serve traffic (DB reachable).

    Used by ECS target-group health checks in prod so a task with a broken DB
    connection is pulled out of rotation even if the process is alive.
    """
    try:
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
        finally:
            # get_connection() returns a live connection; close so we don't
            # starve the pool (or leak a raw connection pre-pool).
            try:
                conn.close()
            except Exception:
                pass
        return {"status": "ready"}
    except Exception as e:
        log.error("readiness_failed", extra={"exc": str(e)})
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "not_ready", "error": str(e)})


# --- Route registration ---
from src.lms_agents.routers import (
    auth, plans, upload, upload_validate, assignments, activities, student_auth,
    grading, analytics, classroom, calendar, credits,
    accommodations, sharing, settings, chat, standards, knowledge, history, admin, videos, games, lulings, design, assignment_manager, onboarding, admin_extended, support, billing, stripe_webhooks, assistant, images, classes, class_intelligence, google_generate,
    canva, clips, dashboard, prebuilt_activities,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(upload_validate.router, prefix="/api/v1")
app.include_router(assignments.router, prefix="/api/v1")
app.include_router(activities.router, prefix="/api/v1")
app.include_router(prebuilt_activities.router, prefix="/api/v1")
app.include_router(student_auth.router, prefix="/api/v1")
app.include_router(grading.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(classroom.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")
app.include_router(credits.router, prefix="/api/v1")
app.include_router(accommodations.router, prefix="/api/v1")
app.include_router(sharing.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(standards.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(videos.router, prefix="/api/v1")
app.include_router(clips.router, prefix="/api/v1")
app.include_router(games.router)  # Games router has its own prefixes including WebSocket
app.include_router(lulings.router, prefix="/api/v1")
app.include_router(design.router, prefix="/api/v1")
app.include_router(assignment_manager.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(admin_extended.router, prefix="/api/v1")
app.include_router(support.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(stripe_webhooks.router)  # No prefix — webhook path is hardcoded
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(images.router, prefix="/api/v1")
app.include_router(classes.router, prefix="/api/v1")
app.include_router(class_intelligence.router, prefix="/api/v1")
app.include_router(google_generate.router, prefix="/api/v1")
app.include_router(canva.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")

# --- Inngest: durable workflow engine ---
import inngest.fast_api
from src.lms_agents.inngest.client import inngest_client
from src.lms_agents.inngest.functions import all_functions

inngest.fast_api.serve(app, inngest_client, all_functions)
