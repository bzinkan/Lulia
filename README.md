# Lulia

**AI-Powered Learning Management System**

Lulia is an AI teaching partner that replaces the need for Teachers Pay Teachers. Teachers upload their curriculum, approve a weekly plan, and Lulia generates everything — lesson plans, worksheets, task cards, interactive activities, live games, videos, and more — all standards-aligned, TpT-quality, and never repeated.

## Architecture

- **16 AI Agents** across 5 crews orchestrated by CrewAI
- **3 LLM Providers**: Claude (reasoning), Gemini (Google Slides + Imagen), AWS Bedrock (embedding)
- **20+ TpT-Quality Templates** with 7 design themes
- **8 Pre-Built Game Shells** + ~15 Claude-generated interactive activity types
- **Three-Tier Standards**: Custom > State (50 + DC) > National (Common Core, NGSS, C3)
- **Generation History**: System never repeats content
- **IEP/504/ELL/Gifted Accommodations**: 3 layers with dignity-preserving design

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Orchestration | CrewAI |
| Primary LLM | Claude API (Anthropic) |
| Google Formats + Video | Gemini API (Google) + Imagen |
| Text Embedding | AWS Bedrock (Titan V2) |
| Backend API | FastAPI (Python) |
| Database | PostgreSQL 16 + pgvector |
| Dashboard | Next.js |
| Worker | APScheduler |
| Video | Gemini Imagen + TTS + ffmpeg |
| Interactive Hosting | S3 + CloudFront |
| Live Games | WebSocket (FastAPI) |
| Dev Environment | Docker Desktop (MinIO) |
| Production | AWS (ECS/Fargate, RDS, S3, SQS, SES, Bedrock) |

## Quick Start (Development)

```bash
# Clone the repo
git clone https://github.com/yourusername/lulia.git
cd lulia

# Copy environment file
cp .env.example .env.development
# Edit .env.development with your API keys

# Start all services
docker-compose up

# Dashboard: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# MinIO Console: http://localhost:9001
```

## Project Structure

```
lulia/
├── src/lms_agents/
│   ├── config/                  # Agent and task YAML definitions
│   │   ├── agents.yaml
│   │   └── tasks.yaml
│   ├── crews/                   # 5 crew files
│   │   ├── planning_crew.py
│   │   ├── assignment_crew.py
│   │   ├── scan_grade_crew.py
│   │   ├── analytics_crew.py
│   │   └── standards_crew.py
│   ├── tools/                   # Agent tools
│   │   ├── rag_search.py
│   │   ├── bedrock_embedding.py
│   │   ├── knowledge_ingestion.py
│   │   ├── generation_history.py
│   │   ├── preview_renderer.py
│   │   ├── calendar_output.py
│   │   ├── accommodation_engine.py
│   │   ├── sharing.py
│   │   ├── standards_db.py
│   │   ├── standards_importer.py
│   │   ├── curriculum_importer.py
│   │   ├── google_classroom.py
│   │   ├── google_drive.py
│   │   ├── google_calendar.py
│   │   ├── gemini_slides.py
│   │   ├── gemini_imagen.py
│   │   ├── video_pipeline.py
│   │   ├── lesson_plan_renderer.py
│   │   ├── template_renderer.py
│   │   ├── interactive_builder.py
│   │   ├── puzzle_generators.py
│   │   ├── curriculum_calendar.py
│   │   ├── ocr_processor.py
│   │   ├── pdf_generator.py
│   │   ├── qr_handler.py
│   │   ├── file_storage.py
│   │   └── credit_manager.py
│   ├── worker/                  # Background worker
│   │   ├── scheduler.py
│   │   ├── plan_dispatcher.py
│   │   ├── template_renderer.py
│   │   ├── video_renderer.py
│   │   ├── scan_watcher.py
│   │   ├── classroom_sync.py
│   │   ├── calendar_sync.py
│   │   ├── history_store.py
│   │   └── notification_handler.py
│   ├── templates/               # Output Template Library (20+)
│   │   ├── worksheet/
│   │   ├── task_cards/
│   │   ├── flashcards/
│   │   ├── bingo/
│   │   ├── word_search/
│   │   ├── crossword/
│   │   ├── escape_room/
│   │   ├── reading_comprehension/
│   │   ├── writing_prompts/
│   │   ├── graphic_organizer/
│   │   ├── anchor_chart/
│   │   ├── quiz_test/
│   │   ├── exit_ticket/
│   │   ├── study_guide/
│   │   ├── sub_plans/
│   │   ├── morning_work/
│   │   ├── homework_packet/
│   │   ├── vocab_cards/
│   │   ├── board_game/
│   │   ├── scavenger_hunt/
│   │   ├── parent_newsletter/
│   │   ├── lab_activity/
│   │   ├── lab_report/
│   │   └── shared_themes/       # 7 design themes
│   │       ├── modern_clean.css
│   │       ├── playful_primary.css
│   │       ├── bold_bright.css
│   │       ├── nature_earth.css
│   │       ├── galaxy_space.css
│   │       ├── seasonal.css
│   │       └── custom.css
│   ├── game_shells/             # 8 pre-built game shells
│   │   ├── gold_rush/
│   │   ├── tower_defense/
│   │   ├── racing/
│   │   ├── battle_royale/
│   │   ├── factory_tycoon/
│   │   ├── space_explorer/
│   │   ├── monster_battle/
│   │   └── classic_quiz_race/
│   ├── models/                  # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── teacher.py
│   │   ├── classes.py
│   │   ├── standards.py
│   │   ├── knowledge.py
│   │   ├── plans.py
│   │   ├── assignments.py
│   │   ├── interactive.py
│   │   ├── grading.py
│   │   ├── credits.py
│   │   ├── accommodations.py
│   │   └── generation_history.py
│   ├── routers/                 # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── plans.py
│   │   ├── upload.py
│   │   ├── assignments.py
│   │   ├── activities.py
│   │   ├── grading.py
│   │   ├── analytics.py
│   │   ├── classroom.py
│   │   ├── calendar.py
│   │   ├── credits.py
│   │   ├── accommodations.py
│   │   ├── sharing.py
│   │   ├── settings.py
│   │   ├── chat.py
│   │   └── auth.py
│   └── main.py                  # FastAPI app entry point
├── dashboard/                   # Next.js frontend (Bolt.new)
├── data/
│   └── state_standards/         # Pre-loaded 50 states + DC
├── game_shells/                 # React game shell source
├── docs/
│   └── architecture-v3.3.docx  # Architecture document
├── scripts/
│   ├── seed_standards.py        # Load state standards into DB
│   ├── seed_templates.py        # Initialize template library
│   └── migrate.py               # Database migrations
├── .claude/
│   └── skills/                  # 9 Claude Code skills
│       ├── crewai-lms/
│       ├── fastapi-lms/
│       ├── rag-pipeline/
│       ├── google-classroom-lms/
│       ├── standards-system/
│       ├── lesson-plan-system/
│       ├── video-pipeline/
│       ├── interactive-system/
│       └── lms-master/
├── .github/
│   └── workflows/
│       └── deploy.yml           # CI/CD pipeline
├── docker-compose.yml           # Local development
├── Dockerfile                   # API + Worker image
├── .env.example                 # Template for environment variables
├── .gitignore
├── requirements.txt
└── README.md
```

## Build Phases

| Phase | Weeks | Milestone |
|-------|-------|-----------|
| 1 | 1-5 | Docker, PostgreSQL+pgvector, Standards system |
| 2 | 6-12 | RAG KB, Upload lanes, Assignment Crew, Dashboard **(MVP)** |
| 3 | 13-19 | Template Library (20+), Generation History |
| 4 | 20-25 | Scan & Grade, Worker, Analytics |
| 5 | 26-33 | Classroom, Lesson Plans, Calendar |
| 6 | 34-38 | Video Pipeline (Imagen), Accommodations |
| 7 | 39-43 | Interactive System (React + WebSocket) |
| 8 | 44-48 | Chat, Onboarding, Sharing, Credits, Polish |

## Documentation

- [Architecture Document (v3.3)](docs/architecture-v3.3.docx) — 1,841 paragraphs, 34 sections
- [Skills Guide](docs/skills-guide.md) — How to use the 9 Claude Code skills

## License

Proprietary — All rights reserved.
