# Lulia — AI-Powered Learning Management System

## What This Project Is
Lulia is an AI-powered LMS that replaces Teachers Pay Teachers. Teachers upload curriculum, approve a weekly plan, and the system generates everything: lesson plans, worksheets, task cards, interactive activities, live games, videos, and more — all standards-aligned, TpT-quality, never repeated.

**Current status**: Phases 1–16 complete. All features built and running locally via Docker Compose. Pre-production — ready for AWS deployment and beta testing.

## Architecture Reference
The complete architecture document is at `docs/architecture-v3.3.docx`. Read the relevant skills in `.claude/skills/` before starting any work — they contain patterns, code examples, and key decisions.

Additional docs:
- `docs/DEVELOPMENT.md` — Local setup, project structure, how to add templates/pages
- `docs/STRIPE_SETUP.md` — Stripe products, webhook setup, test cards
- `docs/PRE_AWS_CHECKLIST.md` — Pre-deployment verification checklist
- `CHANGELOG.md` — All phases documented

## Tech Stack
- **AI Orchestration**: 5 agent crews (Assignment, Planning, Grading, Analytics, Video)
- **LLM Providers**: Claude API (reasoning/content), Gemini 2.5 Flash (Slides/Forms via unified gemini_client.py), AWS Bedrock (embedding), AWS Polly (TTS default), ElevenLabs (TTS premium/cloning)
- **Image Generation**: Replicate Flux 1.1 Pro (Lulings avatars, worksheet images)
- **Backend**: FastAPI (Python 3.12+) with 30+ API routers
- **Database**: PostgreSQL 16 + pgvector (40+ tables)
- **Dashboard**: Next.js 14 (App Router) + Tailwind CSS
- **Real-time**: WebSocket (FastAPI native) + Redis for live games
- **Storage**: MinIO (dev) / S3 (prod) — 6 buckets
- **Payments**: Stripe (subscriptions + credit packs)
- **Dev Environment**: Docker Compose (7 services: api, dashboard, db, minio, redis, worker, createbuckets)
- **Prod Environment**: AWS (ECS/Fargate, RDS, S3, SQS, SES, Bedrock, CloudFront)

## Key Architectural Decisions (Do Not Change)
1. Three LLM providers: Claude (reasoning), Gemini 2.5 Flash (Google Slides/Forms, with Claude Haiku fallback), Bedrock (embedding). Zero overlap.
2. Three-tier standards: Custom > State (50+DC pre-loaded) > National (Common Core, NGSS, C3).
3. Per-procedure standard citations on every lesson plan phase.
4. Generation History prevents content from ever repeating (SHA-256 fingerprinting).
5. Format Agent renders via template library (22 templates + 5 puzzles), not LLM-generated HTML.
6. IEP/504/ELL/Gifted accommodation versions use the SAME template design (dignity principle).
7. Docker Desktop for dev, AWS for prod. Same code, different config.
8. MinIO stands in for S3 locally. Same boto3 calls, different endpoint.
9. API versioned at /api/v1/ from day one.
10. Student PII never sent to LLMs.
11. TTS routing: Polly (default, cheap) → ElevenLabs (premium tier only).
12. Credits are atomic — `SELECT FOR UPDATE` prevents race conditions.
13. Interactive activities are self-contained HTML files (React via CDN, no build step).
14. Live games use Redis for state + WebSocket for real-time sync.

## Project Structure
```
src/lms_agents/
├── config/          # Agent YAML, tasks YAML, pricing configuration
├── crews/           # 5 agent crews: assignment, planning, grading, analytics, video
├── routers/         # 30+ FastAPI route handlers
├── tools/           # 25+ shared tools (RAG, embedding, TTS, Stripe, credit manager, etc.)
├── templates/       # 22 output templates + 5 puzzle generators + shared themes
├── websocket/       # WebSocket game server
├── worker/          # Background worker
└── main.py          # FastAPI app entry point

dashboard/
├── src/app/         # 20+ Next.js App Router pages
│   ├── admin/       # Super admin panel (9 pages)
│   ├── assignments/ # Assignment manager + detail + inbox
│   ├── design/      # WYSIWYG Design Studio
│   ├── planner/     # Weekly Planner
│   └── ...          # billing, games, interactive, videos, etc.
├── src/components/  # Shared React components (Sidebar, ChatSidebar, LulingSelector, etc.)
└── src/lib/         # API client, admin client

scripts/             # DB init, standards import, seed data, Lulings generation, Stripe listener
docs/                # DEVELOPMENT.md, STRIPE_SETUP.md, PRE_AWS_CHECKLIST.md
tests/               # pytest critical path tests (15 tests)
```

## Skills (Read Before Coding)
- `crewai-lms` — Agent definitions, crews, multi-model routing, work order pattern
- `fastapi-lms` — API endpoints, events, database, Docker/AWS
- `rag-pipeline` — pgvector, Bedrock embedding, chunking, knowledge ingestion
- `google-classroom-lms` — OAuth, Classroom, Gemini Slides/Forms, Calendar sync
- `standards-system` — Three-tier hierarchy, state loading, crosswalks
- `lesson-plan-system` — Templates, citations, flexible duration, subject-aware selection
- `video-pipeline` — TTS (Polly/ElevenLabs), slide rendering, ffmpeg assembly
- `interactive-system` — React generation, game shells, WebSocket, student access
- `lms-master` — Architecture hub, all decisions, build timeline
- `dashboard-frontend` — Peach & Amber design system, DM Serif Display + DM Sans fonts

## What's Built (Phases 1–16)

| Phase | What |
|-------|------|
| 1a-b | Docker env, PostgreSQL+pgvector, FastAPI skeleton, Three-tier standards (62K+ loaded) |
| 2a-d | RAG KB (Bedrock embedding), Curriculum dual pipeline, Assignment Generation Crew (5-agent chain), Dashboard MVP |
| 3a-c | 22 output templates, 5 puzzle generators, 4 design themes, Generation History (no-repeat) |
| 4 | Lesson Plan System + Weekly Planner (Path 1 — plan → approve → generate) |
| 5 | Accommodation System (IEP/504/ELL/Gifted with dignity-preserving design) |
| 6 | Google Classroom + Workspace (OAuth, Slides, Forms, Calendar, Drive) |
| 6.5 | MVP Super Admin Panel (overview, teachers, impersonation, costs, health) |
| 7 | Scan & Grade Crew (Claude vision OCR, 5 grading methods, mastery tracking) |
| 8 | Analytics Crew (class/student insights, standards heatmap, adaptive Planner feedback) |
| 9-9.1 | Video Pipeline (Polly + ElevenLabs TTS, slide renderer, ffmpeg, voice cloning) |
| 10 | Interactive Assessment Mode (15 React templates, S3 hosting, student access codes) |
| 11-11.5 | Live Game Mode (8 shells, WebSocket, Redis, Game PIN) + Lulings avatars (50 Flux-generated) |
| 12 | Design Studio (WYSIWYG canvas, 23 component renderers, AI Fill engine) |
| 13 | Assignment Manager (By Class/By Week views, unified grading inbox) |
| 14-14.5 | Chat sidebar, Onboarding wizard, Sharing/Remix, Feature flags, Support tickets, Announcements |
| 15 | Stripe billing (5 tiers, credit system, webhooks, atomic charging) |
| 16 | Local polish (tests, seed data, docs, tablet responsive) |

## Local Development

```bash
docker compose up -d                                    # Start all services
docker compose exec api python scripts/seed_demo_data.py  # Seed demo data
docker compose exec api pytest tests/ -v                  # Run tests (15/15 passing)
```

Dashboard: http://localhost:3001
API Docs: http://localhost:8000/docs
Admin: http://localhost:3001/admin (admin@lulia.com / admin)

## Code Conventions
- Python 3.12+, FastAPI for all API endpoints
- Pydantic v2 for request/response schemas
- Type hints everywhere
- Environment variables via python-dotenv, never hardcoded
- Peach & Amber design system for all frontend (warm tones, DM Serif Display headings, #F97316 primary)
- All generation pages use 3 creation modes: Prompt / Quick Form / From Existing
