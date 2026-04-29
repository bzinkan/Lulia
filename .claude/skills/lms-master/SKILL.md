---
name: lms-master
description: "Use this skill as the master reference for the AI-powered LMS project. Trigger whenever you need overall architectural context, the agent registry, key decisions, build timeline, or when unsure which skill to consult. This is the hub — it knows the full system and points to the right specialized skill."
---

# LMS Master Architecture Reference

## Vision

AI-powered LMS that replaces Teachers Pay Teachers for individual teachers. Teacher uploads materials, approves plans, everything else is automated. System produces TpT-quality worksheets, task cards, interactive activities, optional retained game/video paths, and formal lesson plans — all standards-aligned, curriculum-grounded, never repeated.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Orchestration | CrewAI (Python) |
| Primary LLM | Claude API (Anthropic) |
| Google Formats + Media Experiments | Gemini API (Google) |
| Text Embedding | AWS Bedrock (Titan V2) |
| Backend API | FastAPI (Python) |
| Database | PostgreSQL 16 + pgvector |
| Dashboard | Next.js (Bolt.new) |
| Worker | APScheduler (Python) |
| Video | Strategy undecided: curated library + retained generation/clip paths |
| Interactive Hosting | S3 + CloudFront (static React) |
| Live Games | Backend retained; Arcade UI shelved for launch |
| Dev Environment | Docker Desktop (MinIO, local PG) |
| Prod Environment | AWS (ECS/Fargate, RDS, S3, SQS, SES, CloudFront, Bedrock) |
| School Integration | Google Classroom, Drive, Calendar, Forms APIs |

## Key Decisions (All Locked In)

1. **RAG over NotebookLM** — no public API. Built-in RAG with pgvector + Bedrock embedding.
2. **Three LLM providers**: Claude (reasoning), Gemini (Google formats + interactive/media experiments), Bedrock (embedding). Zero overlap.
3. **Three-tier standards**: Custom > State (50+DC pre-loaded) > National (fallback).
4. **Per-procedure standard citations** on every lesson plan phase.
5. **20+ TpT-quality output templates** with 7 design themes.
6. **Game backend retained, Arcade UI shelved** for initial launch; do not make games launch-critical unless explicitly directed.
7. **Video strategy undecided**: preserve curated library, generated-video pipeline, upload processing, and short-clip/Veo code until product direction is chosen.
8. **Generation History** — system never repeats content. 6-month freshness window.
9. **IEP/504/ELL/Gifted accommodations** — 3 layers (toggle, profiles, per-student). Same template design (dignity).
10. **Two paths**: Path 1 (Plan my week) with previews/approval. Path 2 (Quick generate) skips everything.
11. **Flexible duration**: 1 day (sub plan) to year-long overview.
12. **Subject-aware template selection**: labs for science, passages for ELA, manipulatives for math.
13. **Rich visual previews** before approval. Accept / Modify / Start Over.
14. **Calendar outputs** (all optional): visual PDF, Google Calendar, Classroom topics. Teacher + student versions.
15. **Interactive activities**: Claude generates React → S3 + CloudFront. Assessment mode + Live game mode.
16. **Student access**: Google SSO, Class Code + name, Unique Link, Game PIN. Teacher chooses per class.
17. **Per-student randomization**: question order + answer choice shuffling.
18. **Credit system**: teachers see generation credits, not API tokens. Technical implementation in architecture; pricing in business plan.
19. **Docker Desktop for dev**, AWS (Fargate/RDS/S3/SQS/SES/Bedrock) for prod. Same code, different config.
20. **Teacher onboarding**: Google Sign-In or email/password. 3-step wizard. Instant "wow moment" sample.
21. **Two dashboard layouts**: Subject-Grid or Period-List. Switchable anytime.
22. **Mobile**: full generation on phone, same features as desktop.
23. **Sharing**: teacher-to-teacher via share links. Remix for my class. No admin surveillance.
24. **Notifications**: teacher chooses any combination of email, in-app badge, push.
25. **Single-narrator videos** only. No two-host dialogue.
26. **API-first architecture** for future mobile app / commercialization.

## Which Skill to Use

| Task | Skill |
|------|-------|
| CrewAI agents, crews, tasks, LLM routing | crewai-lms |
| API endpoints, events, database, Docker/AWS | fastapi-lms |
| pgvector, chunking, Bedrock embedding, RAG search | rag-pipeline |
| Google Classroom, Drive, Calendar, Gemini Slides/Forms | google-classroom-lms |
| Three-tier standards, state loading, crosswalks | standards-system |
| Lesson plan templates, flexible duration, citations | lesson-plan-system |
| Retained generated-video path, TTS, ffmpeg, upload processing | video-pipeline |
| React generation, game shells, WebSocket, student access | interactive-system |
| Overall architecture, decisions, build timeline | lms-master (this) |

## Build Timeline (48 weeks)

| Phase | Weeks | Focus |
|-------|-------|-------|
| 1a-c | 1-5 | Docker, PostgreSQL+pgvector, Standards (50 states) |
| 2a-d | 6-12 | RAG KB (Bedrock), Upload lanes, Assignment Gen Crew, Dashboard (MVP) |
| 3a-c | 13-17 | Output Template Library v1 (10 templates + puzzles) |
| 4a-b | 17-19 | Remaining templates (20+ total), Generation History |
| 5 | 20-21 | Scan & Grade Crew |
| 6 | 22-23 | Background Worker |
| 7 | 24-25 | Analytics Crew |
| 8 | 26-27 | Google Classroom + Gemini Slides + Forms + Calendar |
| 9a-c | 28-33 | Lesson Plan System + Planner + Weekly Planner UI + Calendar Outputs |
| 10 | 34-36 | Video Pipeline retained (Imagen/TTS/ffmpeg); launch strategy currently undecided |
| 11 | 37-38 | Accommodation System (IEP/504/ELL/Gifted) |
| 12 | 39-41 | Interactive Assessment Mode (React, S3, student access, randomization) |
| 13 | 42-43 | Live Game backend (WebSocket, game shells, Game PIN); UI shelved for launch |
| 14 | 44-45 | Chat Sidebar + Onboarding + Sharing |
| 15 | 46 | Credit System |
| 16 | 47-48 | Polish, mobile, testing, deployment |

MVP at Week 12. Template Library at Week 17. Full system at Week 48.

## Weekly Cycle

```
Sunday 5 PM:  Planner auto-runs → reads calendar, analytics, KB, Generation History, Template Library
              ↓
              Rich visual preview: worksheet thumbnail, Slides mockup, video frame, interactive preview
              ↓
Sunday PM:    Teacher: Accept / Modify / Start Over
              ↓
              System simultaneously:
                ├── Lesson plan doc → admin Drive
                ├── PDF templates (task cards, worksheets) → print queue
                ├── Google Slides → Classroom
                ├── Interactive assessment → S3 → Classroom link
                ├── Video → library match or retained generated-video fallback, depending on final product direction
                └── Calendar sync (if enabled)
              ↓
Monday AM:    Everything ready. Print. Classroom populated. Interactive links live.
              ↓
Friday:       Paper assessments scanned. Interactive responses collected. Auto-graded.
              ↓
              Analytics updated → Generation History stored → feeds next Sunday's Planner
```
