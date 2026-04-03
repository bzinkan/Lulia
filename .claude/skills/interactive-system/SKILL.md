---
name: interactive-system
description: "Use this skill whenever building interactive assignments, live games, or the student-facing activity platform. Triggers include: generating React components for activities, building pre-built game shells, implementing WebSocket for live games, student access methods (Google SSO, Class Code, Unique Link, Game PIN), per-student randomization, S3+CloudFront hosting for activities, student response collection, or integrating interactive results with the Grading Agent."
---

# Interactive Assignment & Live Game System

## Two Modes

### Assessment Mode (Individual, Tracked)
- Student works at own pace. Graded. Responses tracked per student.
- Claude generates a React component → deployed to S3 + CloudFront as static site.
- Teacher gets a shareable link or pushes to Google Classroom.
- Per-student randomization (question order + answer choice shuffling).
- IEP/504/ELL/Gifted accommodation versions supported.

### Live Game Mode (Class-Wide, Real-Time)
- Whole class plays together. Teacher controls pace. Competitive.
- Pre-built game shells (mechanics built once). Content Agent generates questions that plug in.
- WebSocket for real-time communication (FastAPI native).
- Game PIN access (like Kahoot). No login needed.
- Leaderboard, speed bonuses, streak multipliers, podium celebration.

## Hybrid Architecture

**Pre-Built Game Shells (8 universal, any grade, any subject):**
Mechanics built once in React, reused forever. Content Agent only generates questions.

| Shell | Mechanics |
|-------|-----------|
| Gold Rush | Answer → open chests, steal gold from others |
| Tower Defense | Answer → place towers, wrong = enemies through |
| Racing | Answer → advance car, streak = speed bonus |
| Battle Royale | Wrong = lose a life, last standing wins |
| Factory Tycoon | Answer → earn money, buy upgrades |
| Space Explorer | Answer → fuel rocket, discover planets |
| Monster Battle | Answer → attack, streaks evolve monster |
| Classic Quiz Race | Self-paced, power-ups, memes, streaks |

**Claude-Generated Activities (~15 types, unique every time):**
Claude generates full React components adapted to grade, subject, standards, RAG KB.

Science: Virtual Lab, Ecosystem Simulator, Circuit Builder, Body Systems Explorer
Math: Virtual Store/Restaurant, Math Quest Adventure, Geometry Architect, Virtual Manipulatives
ELA: Choose-Your-Adventure, Grammar Detective, Word Building Workshop, Debate Builder
Social Studies: Historical Decision Sim, Map Explorer, Economics Sim, Government Role-Play

**Universal Interaction Components (building blocks):**
Drag-and-Drop Matching, Sort & Categorize, Label the Diagram, Sequencing/Timeline,
Interactive Fill-in-the-Blank, Enhanced Multiple Choice, Self-Checking Math,
Interactive Graphic Organizer, Flashcard Drill

## Student Access Methods

| Method | How | Best For |
|--------|-----|----------|
| Google Sign-In | Student signs in with Workspace account | Google schools |
| Class Code + Name | Enter class code, pick name from roster, optional PIN | Any school |
| Unique Link | Teacher distributes per-student URL | Homework |
| Game PIN | Enter PIN + display name | Live games |

## Assessment Mode: Technical Flow

```python
# 1. Content Agent generates educational content
content = content_agent.generate(constraints, template="interactive_assessment",
                                  interaction_types=["drag_drop", "self_checking_math"])

# 2. Format Agent calls Claude API to generate React component
react_code = claude_api.messages.create(
    model="claude-sonnet-4-5",
    system="Generate a self-contained React component for an interactive educational activity...",
    messages=[{"role": "user", "content": f"""
        Questions: {json.dumps(content.questions)}
        Interaction types: {content.interaction_types}
        Design theme: {teacher.design_theme}
        Randomization: enabled (seed provided per student)
        Submit endpoint: POST {API_URL}/api/v1/responses/{activity_id}
    """}]
)

# 3. Bundle React component (pre-built shell + generated component injected)
bundle = build_react_bundle(react_code, activity_id)

# 4. Deploy to S3 + CloudFront
s3.upload(bundle, f"lms-activities/{activity_id}/")
cloudfront_url = f"https://cdn.yourdomain.com/activities/{activity_id}/"

# 5. Teacher gets the link
return {"activity_url": cloudfront_url, "activity_id": activity_id}
```

## Live Game Mode: WebSocket Flow

```python
# Teacher launches game
@app.post("/api/v1/activities/{id}/launch")
async def launch_game(activity_id: str):
    pin = generate_game_pin()  # e.g., "847291"
    session = create_game_session(activity_id, pin)
    return {"game_pin": pin, "host_url": f"/game/{session.id}/host"}

# Teacher WebSocket (projected on classroom screen)
@app.websocket("/api/v1/game/{session_id}/host")
async def game_host(ws: WebSocket, session_id: str):
    await ws.accept()
    session = get_session(session_id)
    async for msg in ws.iter_json():
        if msg["action"] == "start":
            await broadcast_to_players(session, {"type": "question", "data": get_question(0)})
        elif msg["action"] == "next":
            session.question_index += 1
            await broadcast_to_players(session, {"type": "question", "data": get_question(session.question_index)})
            await ws.send_json({"type": "leaderboard", "data": session.scores})
        elif msg["action"] == "end":
            await broadcast_to_players(session, {"type": "game_over", "data": get_podium(session)})
            store_game_results(session)  # → Analytics

# Student WebSocket
@app.websocket("/api/v1/game/{session_id}/player")
async def game_player(ws: WebSocket, session_id: str, name: str):
    await ws.accept()
    join_game(session_id, name)
    async for msg in ws.iter_json():
        if msg["action"] == "answer":
            result = score_answer(session_id, name, msg["answer"], msg["time_ms"])
            await ws.send_json({"type": "result", "correct": result.correct, "points": result.points})
```

## Per-Student Randomization

```python
def randomize_for_student(questions, student_seed):
    rng = random.Random(student_seed)
    shuffled = list(questions)
    rng.shuffle(shuffled)  # randomize question order
    for q in shuffled:
        if q.get("choices"):
            rng.shuffle(q["choices"])  # randomize answer choices
    return shuffled
```

Grading Agent de-randomizes using the same seed to score correctly.

## AWS Hosting

- **Assessment Mode**: S3 bucket (lms-activities/) + CloudFront CDN. Static files. Pennies per activity. Unlimited concurrent students.
- **Live Game Mode**: Fargate WebSocket server + ALB with sticky sessions. ~$0.01 per game session.

## Integration Points

- Content Agent generates content (same agent, same RAG KB, same Generation History)
- Format Agent builds React via Claude API (new capability alongside PDF/Slides)
- Grading Agent processes interactive responses alongside paper scans
- Analytics Agent incorporates interactive data into per-standard mastery
- Planner can select interactive formats in weekly plans
- Accommodations apply: simplified UI, reduced questions, larger text
- Google Classroom: activity link posted as assignment
- Credit cost: Interactive Assessment = 4 credits. Live Game = 2 credits.

## Data Model

```sql
CREATE TABLE interactive_activities (
    activity_id UUID PRIMARY KEY, teacher_id UUID, assignment_id UUID,
    activity_type VARCHAR, interaction_types JSONB,
    game_shell_id VARCHAR, questions JSONB,
    access_method VARCHAR, s3_path VARCHAR, cloudfront_url VARCHAR,
    game_pin VARCHAR, is_active BOOLEAN, created_at TIMESTAMP
);

CREATE TABLE student_responses (
    response_id UUID PRIMARY KEY, activity_id UUID,
    student_identifier VARCHAR,
    question_responses JSONB,  -- {question_id, answer, is_correct, time_spent}
    total_score FLOAT, started_at TIMESTAMP, submitted_at TIMESTAMP
);

CREATE TABLE game_sessions (
    session_id UUID PRIMARY KEY, activity_id UUID,
    game_pin VARCHAR, host_teacher_id UUID,
    status VARCHAR, connected_players JSONB,
    question_index INT, scores JSONB,
    started_at TIMESTAMP, ended_at TIMESTAMP
);
```

## Key Rules

1. Game shells are pre-built React apps — only questions change
2. Claude-generated activities are fresh React every time
3. Assessment Mode = static S3 hosting (cheap, scalable)
4. Live Game Mode = WebSocket on Fargate (real-time)
5. Per-student randomization uses deterministic seed for reproducible grading
6. Student PII minimal: only name/code needed, never sent to LLMs
7. Accommodation versions use same visual design (dignity principle)
8. All interactive results feed into unified Grading Review and Analytics
