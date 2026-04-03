---
name: fastapi-lms
description: "Use this skill whenever building the FastAPI backend for the LMS. Triggers include: creating API endpoints, event bus (PostgreSQL dev / SQS prod), job dispatch, OAuth flows, database queries, Docker Compose (dev), AWS deployment (prod), WebSocket for live games, credit system, student access endpoints, or accommodation endpoints."
---

# FastAPI LMS Backend

## Environment Parity: Dev = Docker Desktop, Prod = AWS

| Component | Dev (Docker Desktop) | Prod (AWS) |
|-----------|---------------------|------------|
| Storage | MinIO container | S3 |
| Database | PostgreSQL+pgvector container | RDS PostgreSQL+pgvector |
| Embedding | AWS Bedrock (remote call) | AWS Bedrock (same VPC) |
| Event Bus | PostgreSQL events table | SQS queues |
| Email | Console log | SES |
| Secrets | .env file | Secrets Manager |
| Containers | Docker Compose | ECS/Fargate |

Application code is identical. Only config changes.

## API Endpoints

```
# PLANNING
POST   /api/v1/plans/suggest          # Trigger Planner (accepts duration: day/week/unit/semester/year)
PUT    /api/v1/plans/{id}/approve      # Approve → triggers generation
PUT    /api/v1/plans/{id}/start-over   # Discard and regenerate fresh
GET    /api/v1/plans/{id}/preview      # Rich visual preview thumbnails

# UPLOADS
POST   /api/v1/upload/standards        # → Standards Import Agent
POST   /api/v1/upload/curriculum       # → Calendar + RAG KB
POST   /api/v1/upload/materials        # → RAG KB

# GENERATION
POST   /api/v1/assignments/generate    # Path 2: quick one-off
GET    /api/v1/assignments/{id}        # Assignment detail

# INTERACTIVE ACTIVITIES
POST   /api/v1/activities/generate     # Generate React interactive
GET    /api/v1/activities/{id}         # Activity detail + student link
POST   /api/v1/activities/{id}/launch  # Launch live game → returns game PIN
POST   /api/v1/responses/{id}         # Student submits responses
WS     /api/v1/game/{session}/host     # WebSocket: teacher game control
WS     /api/v1/game/{session}/player   # WebSocket: student game connection

# STUDENT ACCESS
POST   /api/v1/student/auth/google     # Google SSO for students
POST   /api/v1/student/auth/class-code # Class code + name + PIN
GET    /api/v1/student/activity/{token} # Unique link access

# GRADING
POST   /api/v1/scans/upload            # Manual scan upload
GET    /api/v1/reviews/pending          # Unified: paper + interactive

# ACCOMMODATIONS
GET    /api/v1/accommodations/profiles  # List teacher's profiles
POST   /api/v1/accommodations/profiles  # Create IEP/504/ELL/Gifted profile
POST   /api/v1/accommodations/generate  # Generate modified version of assignment

# CREDITS
GET    /api/v1/credits/status           # Credits remaining, tier info
GET    /api/v1/credits/history          # Transaction history
POST   /api/v1/credits/check            # Pre-check before generation

# CALENDAR
POST   /api/v1/calendar/sync-google     # Sync to Google Calendar
POST   /api/v1/calendar/sync-classroom  # Organize Classroom topics
GET    /api/v1/calendar/pdf             # Generate visual calendar PDF

# SHARING
POST   /api/v1/share/{assignment_id}    # Generate share link
GET    /api/v1/share/{token}            # View shared resource
POST   /api/v1/share/{token}/remix      # Copy + modify for my class

# SETTINGS, ANALYTICS, CLASSROOM, CHAT
GET    /api/v1/settings
PUT    /api/v1/settings
GET    /api/v1/analytics/class/{id}
POST   /api/v1/classroom/connect
POST   /api/v1/chat/message
```

## Credit Check Flow

```python
@router.post("/api/v1/credits/check")
async def check_credits(work_orders: list):
    total_needed = sum(calculate_credits(wo) for wo in work_orders)
    account = get_credit_account(teacher_id)
    if account.credits_remaining < total_needed:
        return {"sufficient": False, "needed": total_needed,
                "remaining": account.credits_remaining}
    return {"sufficient": True, "needed": total_needed}

# Credit check happens BEFORE dispatching to CrewAI
@router.put("/api/v1/plans/{plan_id}/approve")
async def approve_plan(plan_id: UUID):
    plan = get_plan(plan_id)
    credits = check_credits(plan.work_orders)
    if not credits["sufficient"]:
        return {"error": "Insufficient credits", **credits}
    deduct_credits(teacher_id, credits["needed"])
    dispatch_generation(plan)
    # Refund on failure handled by worker
```

## WebSocket Game Server

```python
@app.websocket("/api/v1/game/{session_id}/host")
async def game_host(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = get_game_session(session_id)
    async for message in websocket.iter_json():
        if message["action"] == "start":
            await broadcast_question(session, 0)
        elif message["action"] == "next":
            await broadcast_question(session, session.question_index + 1)
        elif message["action"] == "end":
            await broadcast_final_scores(session)

@app.websocket("/api/v1/game/{session_id}/player")
async def game_player(websocket: WebSocket, session_id: str, name: str):
    await websocket.accept()
    session = join_game(session_id, name)
    async for message in websocket.iter_json():
        if message["action"] == "answer":
            score = score_answer(session, name, message)
            await broadcast_leaderboard(session)
```

## Database Schema (Core + New Tables)

```sql
-- See other skills for: standards, knowledge_chunks, lesson_plans, curriculum_calendar

CREATE TABLE generation_history (
    history_id UUID PRIMARY KEY, teacher_id UUID, assignment_id UUID,
    standard_codes JSONB, output_template_id VARCHAR,
    content_fingerprint VARCHAR, content_summary TEXT,
    question_texts JSONB, scenario_context VARCHAR,
    vocabulary_used JSONB, created_at TIMESTAMP
);

CREATE TABLE interactive_activities (
    activity_id UUID PRIMARY KEY, teacher_id UUID, assignment_id UUID,
    activity_type VARCHAR, interaction_types JSONB,
    game_shell_id VARCHAR, questions JSONB, randomization_seed INT,
    access_method VARCHAR, s3_path VARCHAR, cloudfront_url VARCHAR,
    game_pin VARCHAR, is_active BOOLEAN, created_at TIMESTAMP
);

CREATE TABLE student_responses (
    response_id UUID PRIMARY KEY, activity_id UUID,
    student_identifier VARCHAR, question_responses JSONB,
    total_score FLOAT, started_at TIMESTAMP, submitted_at TIMESTAMP
);

CREATE TABLE game_sessions (
    session_id UUID PRIMARY KEY, activity_id UUID,
    game_pin VARCHAR, host_teacher_id UUID,
    status VARCHAR, connected_players JSONB,
    question_index INT, scores JSONB,
    started_at TIMESTAMP, ended_at TIMESTAMP
);

CREATE TABLE credit_accounts (
    account_id UUID PRIMARY KEY, teacher_id UUID,
    tier VARCHAR, credits_remaining INT, credits_total INT,
    billing_cycle_start DATE, billing_cycle_end DATE
);

CREATE TABLE credit_transactions (
    transaction_id UUID PRIMARY KEY, account_id UUID,
    action VARCHAR, credits_spent INT,
    assignment_id UUID, created_at TIMESTAMP
);

CREATE TABLE accommodation_profiles (
    profile_id UUID PRIMARY KEY, teacher_id UUID,
    name VARCHAR, type VARCHAR, modifications JSONB, is_default BOOLEAN
);

CREATE TABLE student_accommodations (
    record_id UUID PRIMARY KEY, teacher_id UUID,
    student_code VARCHAR, profile_id UUID,
    custom_overrides JSONB, notes TEXT
);
```

## Key Rules

1. All file uploads → S3/MinIO first, then events trigger processing
2. Credit check BEFORE dispatching to CrewAI — no cost on rejected requests
3. Refund credits automatically on generation failure
4. Student PII never sent to LLMs — only answer text for grading
5. WebSocket for live games, REST for everything else
6. API versioned at /api/v1/ from day one
