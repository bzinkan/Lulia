# Lulia — AI-Powered Learning Management System

## What This Project Is
Lulia is an AI-powered LMS that replaces Teachers Pay Teachers. Teachers upload curriculum, approve a weekly plan, and the system generates everything: lesson plans, worksheets, task cards, interactive activities, live games, videos, and more — all standards-aligned, TpT-quality, never repeated.

## Architecture Reference
The complete architecture document is at `docs/architecture-v3.3.docx` (1,841 paragraphs, 34 sections). Read the relevant skills in `.claude/skills/` before starting any work — they contain patterns, code examples, and key decisions.

## Tech Stack
- **AI Orchestration**: CrewAI (Python)
- **LLM Providers**: Claude API (reasoning), Gemini API (Slides + Imagen), AWS Bedrock (embedding)
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL 16 + pgvector
- **Dashboard**: Next.js (Bolt.new)
- **Worker**: APScheduler
- **Dev Environment**: Docker Desktop (MinIO for S3)
- **Prod Environment**: AWS (ECS/Fargate, RDS, S3, SQS, SES, Bedrock, CloudFront)

## Key Architectural Decisions (Do Not Change)
1. Three LLM providers: Claude (reasoning), Gemini (Google formats + Imagen), Bedrock (embedding). Zero overlap.
2. Three-tier standards: Custom > State (50+DC pre-loaded) > National (Common Core, NGSS, C3).
3. Per-procedure standard citations on every lesson plan phase.
4. Generation History prevents content from ever repeating.
5. Format Agent is multi-model: Gemini for Slides/Forms, Claude for PDF/React/video.
6. IEP/504/ELL/Gifted accommodation versions use the SAME template design (dignity principle).
7. Docker Desktop for dev, AWS for prod. Same code, different config.
8. MinIO stands in for S3 locally. Same boto3 calls, different endpoint.
9. API versioned at /api/v1/ from day one.
10. Student PII never sent to LLMs.

## Project Structure
- `src/lms_agents/` — All backend Python code
- `src/lms_agents/config/` — CrewAI agent and task YAML definitions
- `src/lms_agents/crews/` — 5 crew implementation files
- `src/lms_agents/tools/` — Agent tools (RAG search, embedding, Classroom, etc.)
- `src/lms_agents/worker/` — Background worker tasks
- `src/lms_agents/models/` — SQLAlchemy database models
- `src/lms_agents/routers/` — FastAPI route handlers
- `src/lms_agents/templates/` — 22 output template folders (HTML/CSS)
- `src/lms_agents/game_shells/` — 8 pre-built React game shells
- `dashboard/` — Next.js frontend
- `data/state_standards/` — Pre-loaded state standards JSON files
- `scripts/` — Database init, seeding, migrations
- `.claude/skills/` — 9 project skills (read these before working on related code)

## Skills (Read Before Coding)
- `crewai-lms` — Agent definitions, crews, multi-model routing
- `fastapi-lms` — API endpoints, events, database, Docker/AWS
- `rag-pipeline` — pgvector, Bedrock embedding, chunking
- `google-classroom-lms` — OAuth, Classroom, Gemini Slides, Imagen
- `standards-system` — Three-tier hierarchy, state loading
- `lesson-plan-system` — Templates, citations, flexible duration
- `video-pipeline` — TTS, Imagen illustrations, ffmpeg
- `interactive-system` — React generation, game shells, WebSocket, student access
- `lms-master` — Architecture hub, all decisions, build timeline

## Build Order
Phase 1a (Weeks 1-2): Docker Compose, PostgreSQL+pgvector, MinIO, FastAPI skeleton, core database schema.
Start here. Get `docker-compose up` working with all 5 services healthy.

## Code Conventions
- Python 3.12+
- FastAPI for all API endpoints
- SQLAlchemy 2.0 for database models
- Pydantic v2 for request/response schemas
- Type hints everywhere
- Async where possible (especially API handlers)
- Environment variables via python-dotenv, never hardcoded
