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
    allow_origins=["http://localhost:3000"],  # Dashboard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


# --- Route registration (uncomment as built) ---
# from src.lms_agents.routers import plans, upload, assignments, activities
# from src.lms_agents.routers import grading, analytics, classroom, calendar
# from src.lms_agents.routers import credits, accommodations, sharing, settings
# from src.lms_agents.routers import chat, auth
#
# app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
# app.include_router(plans.router, prefix="/api/v1", tags=["Plans"])
# app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])
# app.include_router(assignments.router, prefix="/api/v1", tags=["Assignments"])
# app.include_router(activities.router, prefix="/api/v1", tags=["Interactive"])
# app.include_router(grading.router, prefix="/api/v1", tags=["Grading"])
# app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
# app.include_router(classroom.router, prefix="/api/v1", tags=["Classroom"])
# app.include_router(calendar.router, prefix="/api/v1", tags=["Calendar"])
# app.include_router(credits.router, prefix="/api/v1", tags=["Credits"])
# app.include_router(accommodations.router, prefix="/api/v1", tags=["Accommodations"])
# app.include_router(sharing.router, prefix="/api/v1", tags=["Sharing"])
# app.include_router(settings.router, prefix="/api/v1", tags=["Settings"])
# app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
