"""
Game Session Manager — creates and manages live game sessions.

Handles: PIN generation, session lifecycle, player management,
question progression, and score calculation.
"""
import logging
import random
import string
from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection
from src.lms_agents.tools.redis_client import set_game_state, get_game_state, delete_game_state

log = logging.getLogger(__name__)

GAME_SHELLS = {
    "classic_quiz": {"name": "Classic Quiz", "desc": "Kahoot-style MC quiz", "min_players": 1, "max_q": 30},
    "speed_race": {"name": "Speed Race", "desc": "Race to answer 20 questions fastest", "min_players": 2, "max_q": 20},
    "team_tug_of_war": {"name": "Tug of War", "desc": "2 teams pull the rope", "min_players": 4, "max_q": 20},
    "jeopardy": {"name": "Jeopardy", "desc": "5x5 category board", "min_players": 2, "max_q": 25},
    "millionaire": {"name": "Who Wants to Be a Millionaire", "desc": "15 escalating questions", "min_players": 1, "max_q": 15},
    "battle_royale": {"name": "Battle Royale", "desc": "Last student standing", "min_players": 3, "max_q": 20},
    "card_duel": {"name": "Card Duel", "desc": "Math card game", "min_players": 2, "max_q": 20},
    "escape_classroom": {"name": "Escape the Classroom", "desc": "Cooperative puzzle solving", "min_players": 2, "max_q": 10},
}

AVATARS = ["🐻", "🦊", "🐱", "🐶", "🦁", "🐼", "🦄", "🐸", "🐙", "🦋", "🐢", "🐬", "🦉", "🐝", "🌟", "🎯"]


def _generate_pin() -> str:
    """Generate a unique 6-digit Game PIN."""
    return "".join(random.choices(string.digits, k=6))


def create_game_session(
    teacher_id: str,
    assignment_id: str,
    game_shell_id: str = "classic_quiz",
    settings: dict | None = None,
) -> dict:
    """Create a new game session. Returns session info with PIN."""
    if game_shell_id not in GAME_SHELLS:
        return {"error": f"Unknown game shell: {game_shell_id}"}

    # Get assignment content
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM assignments WHERE assignment_id = %s", (assignment_id,))
    assignment = cur.fetchone()
    if not assignment:
        cur.close(); conn.close()
        return {"error": "Assignment not found"}

    questions = assignment["questions"] if isinstance(assignment["questions"], list) else []

    # Generate unique PIN
    pin = _generate_pin()
    session_id = str(uuid4())

    # Format questions for the game
    game_questions = []
    for q in questions:
        game_questions.append({
            "question_number": q.get("question_number", 0),
            "question_text": q.get("question_text", ""),
            "answer": q.get("answer", ""),
            "options": _generate_options(q),
            "standard_code": q.get("standard_code", ""),
            "points": 1000,
        })

    # Store in PostgreSQL
    cur2 = conn.cursor()
    cur2.execute(
        """INSERT INTO game_sessions_v2
           (session_id, teacher_id, assignment_id, game_shell_id, pin, status, settings_json)
           VALUES (%s, %s::uuid, %s::uuid, %s, %s, 'lobby', %s)""",
        (session_id, teacher_id, assignment_id, game_shell_id, pin, Json(settings or {})),
    )
    conn.commit()
    cur.close(); cur2.close(); conn.close()

    # Store live state in Redis
    game_state = {
        "session_id": session_id,
        "pin": pin,
        "game_shell_id": game_shell_id,
        "title": assignment["title"],
        "status": "lobby",
        "players": [],
        "questions": game_questions,
        "current_question": -1,
        "settings": settings or {"timer_seconds": 20, "points_decay": True},
    }
    set_game_state(pin, game_state)

    log.info(f"[Game] Created session {pin} ({game_shell_id}) with {len(game_questions)} questions")

    return {
        "session_id": session_id,
        "pin": pin,
        "game_shell_id": game_shell_id,
        "game_name": GAME_SHELLS[game_shell_id]["name"],
        "question_count": len(game_questions),
        "status": "lobby",
    }


def _generate_options(question: dict) -> list[str]:
    """Generate MC options from a question. Correct answer + 3 distractors."""
    correct = question.get("answer", "")
    # Simple distractors — in production, Content Agent would generate these
    distractors = [f"Not {correct}", f"Almost {correct}", "None of the above"]
    options = [correct] + distractors[:3]
    random.shuffle(options)
    return options


def join_game(pin: str, name: str, avatar: str = "🐻") -> dict:
    """Player joins a game session."""
    state = get_game_state(pin)
    if not state:
        return {"error": "Game not found"}
    if state["status"] != "lobby":
        return {"error": "Game already started"}

    player_id = str(uuid4())
    player = {
        "player_id": player_id,
        "name": name,
        "avatar": avatar,
        "score": 0,
        "answers": [],
    }
    state.setdefault("players", []).append(player)
    set_game_state(pin, state)

    # Store in PostgreSQL
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO game_players (player_id, session_id, name, avatar)
           VALUES (%s, %s::uuid, %s, %s)""",
        (player_id, state["session_id"], name, avatar),
    )
    conn.commit()
    cur.close(); conn.close()

    return {"player_id": player_id, "name": name, "avatar": avatar, "player_count": len(state["players"])}


def start_game(pin: str) -> dict:
    """Teacher starts the game."""
    state = get_game_state(pin)
    if not state:
        return {"error": "Game not found"}
    state["status"] = "playing"
    state["current_question"] = 0
    set_game_state(pin, state)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE game_sessions_v2 SET status = 'playing', started_at = NOW() WHERE pin = %s",
        (pin,),
    )
    conn.commit(); cur.close(); conn.close()

    return {"status": "playing", "current_question": 0, "total_questions": len(state.get("questions", []))}


def answer_question(pin: str, player_id: str, answer: str, time_taken: float = 0) -> dict:
    """Player submits an answer."""
    state = get_game_state(pin)
    if not state:
        return {"error": "Game not found"}

    q_idx = state.get("current_question", 0)
    questions = state.get("questions", [])
    if q_idx >= len(questions):
        return {"error": "No current question"}

    question = questions[q_idx]
    correct = answer.strip().lower() == question["answer"].strip().lower()

    # Points: max 1000, decays with time
    points = 0
    if correct:
        timer = state.get("settings", {}).get("timer_seconds", 20)
        points = max(100, int(1000 * (1 - time_taken / timer))) if state.get("settings", {}).get("points_decay") else 1000

    # Update player score in Redis
    for p in state.get("players", []):
        if p["player_id"] == player_id:
            p["score"] = p.get("score", 0) + points
            p["answers"].append({"question": q_idx, "answer": answer, "correct": correct, "points": points, "time": time_taken})
            break
    set_game_state(pin, state)

    return {"correct": correct, "points": points, "correct_answer": question["answer"]}


def next_question(pin: str) -> dict:
    """Advance to next question."""
    state = get_game_state(pin)
    if not state:
        return {"error": "Game not found"}

    q_idx = state.get("current_question", 0) + 1
    questions = state.get("questions", [])

    if q_idx >= len(questions):
        return end_game(pin)

    state["current_question"] = q_idx
    set_game_state(pin, state)

    q = questions[q_idx]
    return {
        "current_question": q_idx,
        "total_questions": len(questions),
        "question": {
            "question_number": q["question_number"],
            "question_text": q["question_text"],
            "options": q["options"],
        },
    }


def end_game(pin: str) -> dict:
    """End the game and persist results."""
    state = get_game_state(pin)
    if not state:
        return {"error": "Game not found"}

    state["status"] = "finished"
    set_game_state(pin, state)

    players = state.get("players", [])
    sorted_players = sorted(players, key=lambda p: p.get("score", 0), reverse=True)

    # Persist to PostgreSQL
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE game_sessions_v2 SET status = 'finished', ended_at = NOW() WHERE pin = %s",
        (pin,),
    )

    for rank, p in enumerate(sorted_players, 1):
        cur.execute(
            "UPDATE game_players SET final_score = %s, rank = %s, answers_json = %s WHERE player_id = %s",
            (p.get("score", 0), rank, Json(p.get("answers", [])), p["player_id"]),
        )

    # Store results
    avg_score = sum(p.get("score", 0) for p in players) / max(len(players), 1)
    fastest = sorted_players[0]["name"] if sorted_players else ""
    cur.execute(
        """INSERT INTO game_results
           (result_id, session_id, total_questions, total_players, average_score, fastest_player)
           VALUES (%s, %s::uuid, %s, %s, %s, %s)""",
        (str(uuid4()), state["session_id"], len(state.get("questions", [])),
         len(players), avg_score, fastest),
    )
    conn.commit(); cur.close(); conn.close()

    return {
        "status": "finished",
        "leaderboard": [{"rank": i+1, "name": p["name"], "avatar": p["avatar"], "score": p.get("score", 0)} for i, p in enumerate(sorted_players)],
        "total_questions": len(state.get("questions", [])),
        "total_players": len(players),
    }
