# Lulia — AI-Powered Learning Management System

## What This Project Is
Lulia is an AI-powered LMS that replaces Teachers Pay Teachers. Teachers upload curriculum, approve a weekly plan, and the system generates everything: lesson plans, worksheets, task cards, interactive activities, live games, videos, and more — all standards-aligned, TpT-quality, never repeated.

**Current status**: Phases 1–24 complete. All features built and running locally via Docker Compose. Pre-production — ready for AWS deployment and beta testing.

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
2. Three-tier standards: Custom > State (all 50 + DC, ~1.21M standards loaded from Common Standards Project API via `scripts/import_standards.py --all-states`) > National (Common Core loaded, NGSS + C3 pending). All loaded standards are embedded in pgvector via Bedrock Titan v2 for dense retrieval. Active framework joins in standards_alignment use `is_active=true` so chunks get codes from every state simultaneously.
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
15. OER content ingestion uses a shared framework (`content_ingestion_core.py`). Source adapters (OpenStax, LibreTexts, LoC, future) implement extraction only — chunking, embedding, tagging, storage handled by core.
16. Design Studio was SCRAPPED. Assignment generation is the primary content creation flow. PDF export uses Carbone.io for rendering.
17. Class Tabs: each teaching assignment (grade + subject) has its own scoped context. RAG search filters by `class_id` + `teacher` scope + system OER fallback. Per-class intelligence tracks standards covered, vocabulary, activity ratings, misconceptions, pacing.
18. Standards Alignment: all 62K standards are embedded in pgvector. Chunks get dense-retrieval + Claude Haiku judgment to assign `alignment_scores` (strong/partial), `reading_level`, `grade_bands`. Retrieval by standard code + grade band.
19. Canva + Google OAuth are parked until AWS deployment. Features built with local fallbacks (Carbone PDF, built-in slides). Submit both for review once production URL is live.
20. Pedagogy Director: 16-expert matrix (4 grade bands × 4 subjects) routes every work order to a developmental expert. Merged YAML packs (`grade_bands/` base + `subjects/` overlay) are the source of truth. The director emits a Pedagogy Brief via Sonnet that the Assignment, Planning, and Video crews honor as authoritative constraints. Deep-merge semantics: `_overrides` sections merge into their target (so overlays can extend base video/lesson defaults without losing inherited fields). QA Agent has a deterministic post-check that rejects any bracketed image references in question_text.
21. Structured visuals: LLMs emit a `visual` object on each question instead of bracketed text like `[Image: ten-frame]`. The visual renderer converts 19 canonical types (ten_frame, number_bond, fraction_bar, array, bar_model, area_model, number_line, coordinate_grid, function_table, equation_box, base_ten_blocks, counting_objects, data_table, labeled_diagram, letter_box, word_box, handwriting_lines, picture_choice) into inline SVG. Theme-aware via CSS variables. Unknown types fall through to a labeled placeholder so the system never breaks.
22. Reference-grounded generation: every assignment request retrieves real exemplar artifacts (worksheets, slide decks, lesson plans) from the `teacher_archive` / `teacher_reference` / `loc` lanes whose structural shape the Content Agent matches with fresh content. Chunks carry a `reference_metadata` JSONB column populated by Claude Haiku (`reference_analyzer.py`) with artifact_type, visual_density, structural_features, scaffolding_features, question_count_estimate, and a one-sentence content_shape_description. The `reference_retrieval.find_reference_exemplars()` function layers structural filters on top of semantic search with grade-band-aware lane priority (K-2/3-5 exclude openstax; teacher_archive > teacher_reference > oer_textbook > openstax). The Pedagogy Brief's new `reference_exemplar_guidance` section tells the Content Agent which exemplar's shape to match and how. Goal: Lulia does not produce generic AI slop that looks the same K-12 — every output is shape-matched to a real reference the target teacher would recognize.

## Project Structure
```
src/lms_agents/
├── config/          # Agent YAML, tasks YAML, pricing, course_components.json
│   └── pedagogy_packs/             # Phase 22: 16-expert matrix YAMLs
│       ├── grade_bands/            #   k2.yaml, g35.yaml, g68.yaml, g912.yaml
│       └── subjects/               #   {k2,g35,g68,g912}_{math,ela,science,social}.yaml
├── crews/           # 5 agent crews: assignment, planning, grading, analytics, video
├── routers/         # 30+ FastAPI route handlers
├── tools/           # 25+ shared tools (RAG, embedding, TTS, Stripe, credit manager, etc.)
│   ├── content_ingestion_core.py   # Shared chunk→embed→tag→store pipeline
│   ├── content_sources/            # Source adapters (openstax, libretexts, future sources)
│   ├── pedagogy_director.py        # Phase 22: pack loader, router, brief generator
│   ├── visual_renderer.py          # Phase 22: 19 visual types, inline SVG
│   ├── reference_analyzer.py       # Phase 23: Haiku classifier for artifact shape
│   └── reference_retrieval.py      # Phase 23: find_reference_exemplars()
├── templates/       # 22 output templates + 5 puzzle generators + shared themes
├── websocket/       # WebSocket game server
├── worker/          # Background worker
└── main.py          # FastAPI app entry point

dashboard/
├── src/app/         # 20+ Next.js App Router pages
│   ├── admin/       # Super admin panel (9 pages)
│   ├── assignments/ # Assignment manager + detail + inbox
│   ├── design/      # WYSIWYG Design Studio (157 component renderers)
│   ├── planner/     # Weekly Planner
│   └── ...          # billing, games, interactive, videos, etc.
├── src/components/  # Shared React components
│   └── design/      # ComponentRenderers.jsx (157), ComponentEditors.jsx (math toolbar, shapes)
└── src/lib/         # API client, admin client

scripts/             # DB init, standards import, seed data, Lulings generation, Stripe listener
├── ingest.py        # Unified CLI: ingest.py openstax | libretexts | loc | status
├── ingest_openstax.py   # OpenStax-specific CLI (backwards compat)
├── ingest_libretexts.py # LibreTexts-specific CLI (backwards compat)
├── align_standards.py   # Standards embedding + chunk alignment CLI
├── migrate_class_tabs.py        # class_id columns migration
├── migrate_class_intelligence.py # class_intelligence table migration
├── migrate_canva.py             # canva OAuth columns migration
├── ingest_local_references.py   # Ingest Teaching/ + K-8 material/ from bind-mounted /refs/
├── embed_standards_parallel.py  # Parallel standards embedder (ThreadPoolExecutor, 24 workers)
└── align_standards_offline.py   # Provider-agnostic chunk alignment (prepare/submit/poll/writeback/run-sync)
docs/                # DEVELOPMENT.md, STRIPE_SETUP.md, PRE_AWS_CHECKLIST.md
tests/               # pytest critical path tests (15 tests)
data/content/        # Local OER content storage (gitignored, S3 in prod)
```

## Content Source Locations

All ingested content lives in two places: raw files (where applicable) and the `knowledge_sources` / `knowledge_chunks` tables in Postgres. Every source is identified by its `upload_lane` value. Teacher-scoped lanes are gated by `teacher_id` + `scope='teacher'` so RAG search only surfaces them to the owning teacher.

| Source | `upload_lane` | Raw files | Ingestion command |
|--------|---------------|-----------|-------------------|
| **OpenStax** | `openstax` | Host: `data/content/openstax/` (gitignored, S3 in prod). Cloned as full git repos. Catalog in `openstax_catalog` table. | `docker compose exec api python scripts/ingest.py openstax` |
| **LibreTexts** | `libretexts` | None — Playwright scrapes pages, chunks go straight to DB. | `docker compose exec api python scripts/ingest.py libretexts` |
| **Library of Congress** | `loc` | None — JSON API → chunks go straight to DB. Curated topic list in `src/lms_agents/tools/content_sources/loc.py`. | `docker compose exec api python scripts/ingest.py loc --all-curated` |
| **teacher_archive** (Brian's own teaching materials) | `teacher_archive`, `scope='teacher'` | Host: `C:/Users/zinka/OneDrive/Desktop/Lulia Reference Material/Teaching/`. Bind-mounted read-only into api container at `/refs/Teaching/` via `docker-compose.yml`. | `docker compose exec api python scripts/ingest_local_references.py --folder teaching` |
| **teacher_reference** (free K-8 reference samples) | `teacher_reference`, `scope='teacher'` | Host: `C:/Users/zinka/OneDrive/Desktop/Lulia Reference Material/K-8 material/`. Bind-mounted at `/refs/K-8 material/`. | `docker compose exec api python scripts/ingest_local_references.py --folder k8` |

Quick check of what's in the KB today:
```bash
docker compose exec api python scripts/ingest.py status
```

The ingestion pipeline is idempotent — each source gets a deterministic `name` and re-running any command will skip already-ingested items. To re-ingest a single source, delete its row from `knowledge_sources` (cascade will clear chunks) and re-run.

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
| 17 | OER Content Ingestion Framework: shared core pipeline, OpenStax adapter (82 books, CNXML parsing), LibreTexts adapter (Playwright scraping), LoC adapter (primary sources), unified CLI, 40K+ RAG chunks |
| 18 | Standards Alignment Agent: 1.21M standards (50 states + DC + Common Core) loaded from Common Standards Project API, all embedded to pgvector via Bedrock Titan v2 (HNSW index on `standards.embedding`). Two-step chunk alignment (dense retrieval + LLM judgment) via `scripts/align_standards_offline.py` — provider-agnostic (OpenAI/Anthropic/Groq/Ollama), merge-safe writeback (grade_bands + standards_tags UNIONed, never overwritten; reference_metadata untouched). 33K+ chunks aligned with reading_level + grade_bands + alignment_scores. retrieve_for_standard() API. |
| 19 | Class Tabs + Per-Class Intelligence: class_id FK on knowledge_sources/videos/templates, CRUD router, RAG scoping, per-class standards/vocab/ratings tracking, auto-extraction from assignments, AI context prompts |
| 20 | Design Studio SCRAPPED. Replaced with generation-first assignment flow. Carbone.io integrated for PDF rendering. Google Slides + Forms pages added. Canva OAuth built but parked (needs AWS). |
| 21 | Google Slides/Forms pages, Canva Connect API OAuth flow (OC-AZ1rX8nIER1H), video pipeline fix (hardcoded grade/subject bug), Content Library hides system OER, Sidebar updated |
| 22 | Pedagogy Director + 16-expert matrix (K-2/3-5/6-8/9-12 × math/ELA/science/social), 20 YAML pedagogy packs (~5,800 lines), brief generator wired into Assignment/Planning/Video crews. Structured visuals: 19 inline-SVG visual types (ten_frame, number_bond, fraction_bar, array, bar_model, area_model, number_line, coordinate_grid, function_table, equation_box, base_ten_blocks, counting_objects, data_table, labeled_diagram, letter_box, word_box, handwriting_lines, picture_choice). Deterministic QA bracket-detector. Fixed hardcoded grade_level='4' bug in planning_crew.approve_plan. All 4 grade bands live-verified against Anthropic API. |
| 24 | Nationwide standards + full-KB alignment: imported all 50 states + DC (1.21M state standards) from Common Standards Project API. Built `scripts/embed_standards_parallel.py` (24-worker ThreadPoolExecutor, 10x speedup). Built `scripts/align_standards_offline.py` with provider-agnostic dispatch, merge-safe writeback (grade_bands + standards_tags UNIONed via SQL, reference_metadata provably untouched). Ingested 1,134 local reference files (Teaching/ + K-8 material/) into teacher-scoped knowledge base via `scripts/ingest_local_references.py`. Created HNSW index on `standards.embedding`. Fixed 2 FK violation bugs in `import_standards.py`, subject mismatch filter, and Haiku JSON trailing-prose parser. |
| 23 | Reference-grounded generation: `reference_metadata` JSONB column on `knowledge_chunks` (migration, GIN + partial indexes). `reference_analyzer.py` classifies sources via Haiku into artifact_type + structural/scaffolding features + content_shape_description. `reference_retrieval.py` finds real worksheets/slide decks/lesson plans by structural shape from `teacher_archive` / `teacher_reference` lanes with grade-band-aware lane priority (K-2/3-5 exclude openstax). Pedagogy Brief extended with `reference_exemplar_guidance` section. Assignment Crew pre-fetches exemplars and passes them to the director. Content Agent system prompt updated to treat exemplar shape as authoritative template. A/B test (`test_reference_grounded_generation.py`) validated QA score delta +27 vs un-grounded baseline on 6-8 Earth Science rock cycle fixture. |

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
