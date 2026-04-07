# Changelog

## Phase 16 — Local Polish (2026-04-07)
- Added demo data seed script (scripts/seed_demo_data.py)
- Added critical path test suite (tests/test_critical_paths.py)
- Created project documentation (ARCHITECTURE.md, DEVELOPMENT.md, PRE_AWS_CHECKLIST.md)
- Fixed CORS for tablet Safari
- Added tablet responsive breakpoints

## Phase 15 — Stripe Billing + Credit System (2026-04-07)
- Stripe SDK integration with test mode products
- 5-tier subscription system (Free/Basic/Plus/Premium/Max)
- Atomic credit charging with race condition prevention
- Stripe webhook handler for subscription lifecycle
- Credit packs (50/150/500/1500) via Stripe checkout
- Teacher billing dashboard with credit tracking

## Phase 14.5 — Full Super Admin Dashboard (2026-04-07)
- Content moderation queue
- Support ticket system
- Feature flags (9 seeded)
- Announcements system
- Billing placeholder views

## Phase 14 — Chat Sidebar + Onboarding + Sharing (2026-04-07)
- AI chat assistant with function calling
- Teacher onboarding wizard
- Assignment sharing with remix system
- Community page

## Phase 13 — Assignment Manager (2026-04-07)
- By Class / By Week views
- Unified grading inbox
- Quick actions (duplicate, reschedule, archive)
- Class management page

## Phase 12 — Design Studio (2026-04-07)
- Drag-and-drop template builder
- AI Fill engine (Claude fills canvas components)
- 19 design components
- Custom template CRUD

## Phase 11.5 — Lulings (2026-04-07)
- 50 custom Flux-generated avatars
- 6 character categories
- LulingSelector component
- Replicate integration

## Phase 11 — Live Game Mode (2026-04-07)
- 8 game shells (Classic Quiz, Speed Race, etc.)
- WebSocket game server
- Redis session management
- Game PIN system with student join flow

## Phase 10 — Interactive Assessment (2026-04-06)
- 15 React activity templates
- Self-contained HTML activities on MinIO
- Student access via codes (no auth)
- Submission tracking

## Phase 9.1 — TTS Provider Refactor (2026-04-06)
- AWS Polly as default (cheaper)
- ElevenLabs as premium tier
- Provider-aware caching

## Phase 9 — Video Pipeline (2026-04-06)
- ElevenLabs TTS + voice cloning
- Slide renderer (1920x1080 Pillow)
- ffmpeg video assembly
- 4 preset voices + custom

## Phase 8 — Analytics Crew (2026-04-06)
- Class/student analytics
- Standards heatmap
- AI-generated insights
- Adaptive planner feedback loop

## Phase 7 — Scan & Grade Crew (2026-04-06)
- Claude vision OCR
- 5 grading methods (auto, scan, upload, manual, digital)
- Handwriting confidence scoring
- Student mastery tracking

## Phase 6.5 — MVP Super Admin (2026-04-06)
- Admin authentication + audit log
- Teacher management + impersonation
- System health + cost tracking

## Phase 6 — Google Classroom Integration (2026-04-06)
- OAuth 2.0 with encrypted token storage
- Classroom API (courses, push assignments)
- Gemini Slides + Google Forms
- Calendar sync

## Phase 5 — Accommodation System (2026-04-06)
- IEP/504/ELL/Gifted profiles
- Same-template dignity principle
- 5 default profiles

## Phase 4 — Lesson Plan + Weekly Planner (2026-04-06)
- Planner agent with curriculum calendar awareness
- Subject-aware template selection
- Accept/Modify/Start Over workflow

## Phase 3c — Design Themes (2026-04-06)
- 22 templates total
- 4 design themes via CSS variables
- Theme switching

## Phase 3b — Puzzle Generators + Generation History (2026-04-06)
- 5 puzzle generators (word search, crossword, etc.)
- No-repeat system with fingerprinting

## Phase 3a — Template Library v1 (2026-04-06)
- 10 professional templates
- Template renderer engine

## Phase 2d — Dashboard MVP (2026-04-04)
- Next.js 14 with Tailwind CSS
- 5 pages (home, new assignment, list, detail, library)

## Phase 2c — Assignment Generation Crew (2026-04-04)
- 5-agent chain (Curriculum → Content → Rubric → QA → Format)
- QA rejection loop with retries

## Phase 2b — Curriculum Dual Pipeline (2026-04-04)
- Claude Haiku pacing extraction
- Calendar + RAG KB dual feed

## Phase 2a — RAG Knowledge Base (2026-04-04)
- Bedrock Titan V2 embedding
- Document ingestion (PDF, DOCX, URL)
- pgvector cosine similarity search

## Phase 1b — Standards System (2026-04-04)
- Common Standards Project API integration
- Three-tier priority (Custom > State > National)
- Ohio + Common Core loaded

## Phase 1a — Development Environment (2026-04-03)
- Docker Compose with 5 services
- PostgreSQL + pgvector
- MinIO for S3
- FastAPI skeleton with 39 stubbed routes
