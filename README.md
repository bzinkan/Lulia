# Lulia Lesson Lab

**AI-powered LMS for individual K-12 teachers.** Upload your curriculum, approve a weekly plan, and Lulia generates everything — lesson plans, worksheets, interactive activities, videos, and grading — all standards-aligned, never repeated.

> Pre-production. Phases 1–28 complete. Running locally via Docker Compose; ready for AWS deployment.

---

## What it does

| Surface | What it produces |
|---|---|
| **Planner** | A weekly plan from your curriculum + state standards. Per-day refinement before generation. |
| **Print & Go** | One-shot worksheet generator with live standards auto-match. |
| **Interactive activities** | Six structured engines (crossword, word search, flashcards, timeline, number line, fill-in-blank) where Gemini emits data only — engine code is human-authored, so no LLM-written JS can crash at runtime. Plus an **artifact mode** where Gemini-2.5-Pro writes a full HTML file for ad-hoc topics (MCQ, drag-drop, hotspot, etc.) with a validator + retry guard. |
| **Video Library** | Curated catalog of teacher uploads, YouTube embeds (Standard YT License), and public-domain MP4s — not on-demand compute. Generated videos are the fallback when no library match exists. |
| **Grading** | Claude vision OCR + 5 grading methods + mastery tracking, surfaced in the unified Grades tab. |
| **Calendar / Curriculum / Analytics** | Living curriculum tracking, school-calendar overlay, class-mastery and standards-coverage views. |
| **Image Library** | Teacher uploads + Wikimedia Commons fallback, semantically searchable via Gemini-vision captioning on upload. |

> ⚠ **Live Games / Arcade is shelved** for the initial launch (Phase 28). The 16 game shells, the `/games` / `/play` / `/join` UI, and the Arcade tab are removed from the dashboard. The backend (`routers/games.py`, `websocket/game_server.py`, `tools/game_session_manager.py`, the `/api/v1/games/*` endpoints, the `arcade_*` and `game_*` tables) stays intact — re-enabling is a frontend-only effort.

## Tech stack

| Component | Technology |
|---|---|
| Orchestration | 5 agent crews (Assignment, Planning, Grading, Analytics, Video) — direct Anthropic SDK chain, no CrewAI dependency |
| LLM providers | Claude (reasoning, content, vision OCR), Gemini 2.5 Pro (interactive content + artifact HTML + image captioning), Gemini 2.5 Flash Image (diagrams), AWS Bedrock Titan v2 (embedding) |
| Backend | FastAPI (Python 3.12+), 30+ routers, shared psycopg2 connection pool |
| Auth | bcrypt + JWT (HS256). `Depends(require_teacher)` on protected routes; `DEV_AUTH_BYPASS=1` keeps the legacy `?teacher_id=…` query/form/json fallback working in dev. |
| Database | PostgreSQL 16 + pgvector + pg_trgm (40+ tables; alembic migrations from a stamped baseline) |
| Dashboard | Next.js 14 App Router, Retro Earth design system (DM Serif Display + Nunito, coral/sage/teal/mustard palette, 3D Pillow nav icons) |
| Real-time | FastAPI WebSocket (game backend, currently dormant); Redis for game session state |
| Storage | MinIO in dev, S3 in prod — 6 buckets (`lulia-uploads`, `-generated`, `-scans`, `-templates`, `-activities`, video library) |
| Workflows | Inngest dev container (8288) — durable plan-approval, video upload processing |
| Rate limiting | slowapi (in-memory in dev, Redis-backed in prod via `RATE_LIMIT_STORAGE_URI`) |
| Payments | Stripe subscriptions + credit packs, atomic charging via `SELECT FOR UPDATE` |
| Production | AWS ECS/Fargate, RDS, S3, SQS, SES, Bedrock, CloudFront |

## Quick start (development)

```bash
# 1. Clone + env
git clone https://github.com/bzinkan/Lulia.git
cd Lulia
cp .env.example .env.development           # then edit with your API keys

# 2. Required env vars to fill in:
#    ANTHROPIC_API_KEY      — Claude (content + grading + vision)
#    GOOGLE_GEMINI_API_KEY  — Gemini (interactive + image captioning)
#    JWT_SECRET             — 48+ char random string for auth tokens
#    AWS_*                  — only if you want Bedrock embedding locally
#    STRIPE_*               — only if testing billing
# Everything else has a sensible local default.

# 3. Start the stack
docker compose up -d

# 4. Seed demo data + run the test suite
docker compose exec api python scripts/seed_demo_data.py
docker compose exec api pytest tests/ -v
```

URLs after `docker compose up`:

| Service | URL |
|---|---|
| Dashboard | http://localhost:3001 |
| API | http://localhost:8000 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 (`minioadmin` / `minioadmin`) |
| Inngest dev | http://localhost:8288 |
| Postgres | localhost:5433 (lulia/lulia/devpassword) |

## Project structure

```
src/lms_agents/
├── config/             Agent YAML, pricing, course components, 20 pedagogy packs
├── crews/              5 agent crews (assignment, planning, grading, analytics, video)
├── inngest/            Durable workflow definitions
├── routers/            30+ FastAPI route handlers
├── tools/              25+ shared tools — RAG, embedding, TTS, Stripe, auth, image library, structured templates
├── templates/          22 worksheet templates + 5 puzzle generators + shared themes
├── websocket/          Game server (kept; UI shelved)
└── main.py             FastAPI app entry point

dashboard/
├── src/app/            20+ Next.js App Router pages (login, dashboard home, planner, calendar, interactive, videos, grades, …)
├── src/components/     Shared React components (StandardsPickerModal, EditActivityModal, …)
└── src/lib/            API client (Bearer auth attached automatically), domain helpers

scripts/                 DB init, standards import, seed data, alembic baseline, content ingestion CLIs
tests/                   pytest critical-path + tenant-isolation + html-security tests
docs/                    DEVELOPMENT.md, STRIPE_SETUP.md, PRE_AWS_CHECKLIST.md, CHANGELOG.md
data/content/            Local OER content (gitignored, S3 in prod)
```

## Auth model

- **Registration** → `POST /api/v1/auth/register {email, password, name}` → returns JWT.
- **Login** → `POST /api/v1/auth/login {email, password}` → returns JWT.
- **Current user** → `GET /api/v1/auth/me` with `Authorization: Bearer <token>`.
- **Dashboard** stores the token in `localStorage` (`lulia.auth.token`) and `apiFetch` attaches it on every request. A 401 from any protected route auto-clears the token and routes to `/login`.
- **Tenant isolation** — every CRUD endpoint that returns or mutates a tenant resource uses `Depends(require_teacher)` plus `assert_owner_or_403` on the row's `teacher_id`. Tested in `tests/test_tenant_isolation.py`.
- **Dev bypass** — set `DEV_AUTH_BYPASS=1` (default in `.env.example`) to allow legacy `?teacher_id=<uuid>` queries when no Authorization header is present. **Set `DEV_AUTH_BYPASS=0` in staging/prod.**

## Three-tier standards

1. **Custom** (teacher-specific) — uploaded pacing guides parsed by Haiku
2. **State** — all 50 states + DC, ~1.21M standards loaded from Common Standards Project, embedded via Bedrock Titan v2 in pgvector with HNSW index
3. **National** — Common Core loaded; NGSS + C3 pending

Active framework joins use `is_active=true` so a single chunk gets codes from every state simultaneously. Retrieve by code + grade band via `tools/standards_retrieval`.

## Generation pipelines

- **Worksheet / lesson plan / quiz / video** — full Sonnet crew (Curriculum → Pedagogy Director → Content → Rubric → QA → Format).
- **Interactive activities** — Gemini-only fast path:
  - **Structured templates** (crossword, word_search, flashcards, timeline, number_line, fill_in_blank) — Gemini emits a small JSON of words/cards/events/sentences; the React engine is in `src/lms_agents/tools/structured_*.py`. Word-bank toggle on crossword + fill-in-blank for younger / scaffolded use.
  - **Artifact mode** — Gemini 2.5 Pro emits a complete self-contained HTML file when no structured template fits. Validated for balanced JSX braces + suspicious patterns (external scripts, document.cookie, eval) + 1-shot retry on failure.
- **Hotspot diagrams** — Gemini 2.5 Flash Image generates the diagram, Gemini 2.5 Pro vision annotates pixel-perfect click regions; a curated SVG path is preferred for canonical anatomy where the model knows the structure cold.

## Common operations

```bash
# Run a specific test file
docker compose exec api pytest tests/test_tenant_isolation.py -v

# Apply a migration manually
docker compose exec api python scripts/migrate_teacher_password_hash.py

# Generate a structured crossword end-to-end
docker compose exec api python -c "
from src.lms_agents.tools.structured_crossword import generate_crossword_activity
print(generate_crossword_activity(
    topic='Plant cell organelles', grade='5', subject='Science',
    teacher_id='00000000-0000-0000-0000-000000000001',
    class_id='00000000-0000-0000-0000-000000000010',
    standards=[], question_count=8))"

# Check what's in the knowledge base
docker compose exec api python scripts/ingest.py status
```

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — Architectural decisions, build phases, "do not change" rules
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — local setup, project structure, adding templates/pages
- [`docs/STRIPE_SETUP.md`](docs/STRIPE_SETUP.md) — Stripe products, webhook setup, test cards
- [`docs/PRE_AWS_CHECKLIST.md`](docs/PRE_AWS_CHECKLIST.md) — pre-deployment verification (now also tracked as a release-gate label on PRs)
- [`CHANGELOG.md`](CHANGELOG.md) — every phase documented

## License

All rights reserved. Pre-launch / private.
