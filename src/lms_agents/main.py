"""
Lulia — AI-Powered Learning Management System
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Lulia API",
    description="AI-Powered LMS — 16 agents, 20+ templates, interactive activities, live games",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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
    auth, plans, upload, assignments, activities, student_auth,
    grading, analytics, classroom, calendar, credits,
    accommodations, sharing, settings, chat, standards, knowledge, history, admin, videos,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
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
