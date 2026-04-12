"""
Lulia — AI-Powered Learning Management System
FastAPI Application Entry Point
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    """Auto-apply any un-run migrate_*.py scripts on API boot.
    Controlled by AUTO_MIGRATE env var (default on).
    Set FAIL_ON_MIGRATION_ERROR=true in prod to hard-fail on bad migrations.
    """
    if os.environ.get("AUTO_MIGRATE", "true").lower() != "true":
        log.info("[boot] AUTO_MIGRATE disabled, skipping migrations")
        return
    try:
        from scripts.run_migrations import run_pending
        result = run_pending()
        log.info(
            f"[boot] migrations: {len(result['ran'])} applied, "
            f"{len(result['skipped'])} already-applied, "
            f"{len(result['failed'])} failed"
        )
        if result["failed"] and os.environ.get("FAIL_ON_MIGRATION_ERROR", "false").lower() == "true":
            raise RuntimeError(f"Migration failures: {[n for n,_ in result['failed']]}")
    except Exception as e:
        log.error(f"[boot] migration runner error: {e}")
        if os.environ.get("FAIL_ON_MIGRATION_ERROR", "false").lower() == "true":
            raise

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


# --- Route registration ---
from src.lms_agents.routers import (
    auth, plans, upload, upload_validate, assignments, activities, student_auth,
    grading, analytics, classroom, calendar, credits,
    accommodations, sharing, settings, chat, standards, knowledge, history, admin, videos, games, lulings, design, assignment_manager, onboarding, admin_extended, support, billing, stripe_webhooks, assistant, images, classes, class_intelligence, google_generate,
    canva, clips,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(upload_validate.router, prefix="/api/v1")
app.include_router(assignments.router, prefix="/api/v1")
app.include_router(activities.router, prefix="/api/v1")
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
