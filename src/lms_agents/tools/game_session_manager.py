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
    # Phase 1 — fully playable
    "quiz_race":        {"name": "Quiz Race",         "desc": "Kahoot-style MC, fastest = most points",             "min_players": 1, "max_q": 30, "phase": 1, "icon": "game_quiz_race.png"},
    "jeopardy":         {"name": "Jeopardy",          "desc": "5x5 category board, teacher or AI picks",           "min_players": 3, "max_q": 25, "phase": 1, "icon": "game_jeopardy.png"},
    "bingo_blitz":      {"name": "Bingo Blitz",       "desc": "5x5 bingo card, teacher calls questions",            "min_players": 1, "max_q": 30, "phase": 1, "icon": "game_bingo.png"},
    # Phase 2 — coming soon
    "millionaire":      {"name": "Millionaire",       "desc": "15 escalating questions with 3 lifelines",           "min_players": 1, "max_q": 15, "phase": 2, "icon": "game_millionaire.png"},
    "battle_royale":    {"name": "Battle Royale",     "desc": "Wrong answer = out, last standing wins",            "min_players": 5, "max_q": 20, "phase": 2, "icon": "game_battle_royale.png"},
    "team_tug_of_war":  {"name": "Team Tug of War",   "desc": "Teams pull a rope with correct answers",             "min_players": 6, "max_q": 20, "phase": 2, "icon": "game_tug_of_war.png"},
    "memory_match":     {"name": "Memory Match",      "desc": "Match question-answer pairs, speed bonus",           "min_players": 1, "max_q": 20, "phase": 2, "icon": "game_memory.png"},
    # Phase 3 — coming soon
    "speed_rush":       {"name": "Speed Rush",        "desc": "Rapid-fire sprint, who finishes deck fastest",       "min_players": 1, "max_q": 30, "phase": 3, "icon": "game_speed_rush.png"},
    "escape_room":      {"name": "Escape Room",       "desc": "Cooperative puzzle, unlock rooms with answers",     "min_players": 2, "max_q": 15, "phase": 3, "icon": "game_escape.png"},
    "card_duel":        {"name": "Card Duel",         "desc": "1v1 turn-based elimination",                         "min_players": 2, "max_q": 20, "phase": 3, "icon": "game_card_duel.png"},
    "wheel_spin":       {"name": "Wheel Spin",        "desc": "Spin for category, answer question",                 "min_players": 1, "max_q": 20, "phase": 3, "icon": "game_wheel.png"},
    "tournament":       {"name": "Tournament Bracket","desc": "Single-elimination between students",                "min_players": 4, "max_q": 20, "phase": 3, "icon": "game_tournament.png"},
}

AVATARS = ["🐻", "🦊", "🐱", "🐶", "🦁", "🐼", "🦄", "🐸", "🐙", "🦋", "🐢", "🐬", "🦉", "🐝", "🌟", "🎯"]


def _generate_pin() -> str:
    """Generate a unique 6-digit Game PIN."""
    return "".join(random.choices(string.digits, k=6))


def create_game_session(
    teacher_id: str,
    game_shell_id: str = "quiz_race",
    class_id: str | None = None,
    question_source: dict | None = None,
    settings: dict | None = None,
    is_replay: bool = False,
) -> dict:
    """
    Create a new game session. Returns session info with PIN.

    question_source: { type: 'assignment'|'standards'|'custom'|'cached', ... }
      - assignment: { assignment_id }
      - standards:  { standards: [codes], question_count }
      - custom:     { prompt, question_count }
      - cached:     { cached_questions, question_count } — used by replay path
    """
    if game_shell_id not in GAME_SHELLS:
        return {"error": f"Unknown game shell: {game_shell_id}"}

    question_source = question_source or {"type": "assignment"}
    source_type = question_source.get("type", "assignment")

    # Resolve questions per source type
    title = "Live Game"
    assignment_id_for_row: str | None = None
    generated_questions_cache: list | None = None

    if source_type == "assignment":
        assignment_id = question_source.get("assignment_id")
        if not assignment_id:
            return {"error": "assignment_id required for type='assignment'"}
        raw_questions, title = _load_assignment(assignment_id)
        if not raw_questions:
            return {"error": "Assignment not found or has no questions"}
        assignment_id_for_row = assignment_id

    elif source_type == "standards":
        standards = question_source.get("standards") or []
        count = question_source.get("question_count", 15)
        if not standards:
            return {"error": "standards list required for type='standards'"}
        raw_questions, matched_assignment_ids = _load_from_standards(teacher_id, standards, count)
        if raw_questions:
            title = f"Game: {', '.join(standards[:3])}{'...' if len(standards) > 3 else ''}"
            if len(set(matched_assignment_ids)) == 1:
                assignment_id_for_row = matched_assignment_ids[0]
        else:
            # Fall through to Haiku generation keyed to the selected standards.
            from src.lms_agents.tools.credit_manager import charge_credits, grant_credits
            from src.lms_agents.config.pricing import CREDIT_COSTS
            cost = CREDIT_COSTS.get("live_game_custom_questions", 2)
            charge = charge_credits(
                teacher_id, cost,
                reference_type="live_game_standards_fallback",
                description=f"Live Game from standards ({count} questions, no match found)",
            )
            if not charge["success"]:
                return {
                    "error": charge.get("error", "Credit charge failed"),
                    "reason": "insufficient_credits",
                    **charge,
                }
            # Use the class's actual grade + subject (not hardcoded defaults)
            class_grade, class_subject = _class_grade_subject(class_id)
            # Look up real descriptions so Haiku knows what standard codes mean
            standard_details = _fetch_standard_descriptions(standards)
            # Warn early if no descriptions were found — Haiku will guess wildly otherwise
            missing_descriptions = [d for d in standard_details if not d.get("description") or d["description"] == "(description not found)"]
            if missing_descriptions:
                log.warning(
                    f"[Games] Standards missing descriptions — Haiku may drift off-subject. "
                    f"Missing: {[d['code'] for d in missing_descriptions]}"
                )
            topic_from_standards = (
                f"SUBJECT: {class_subject} (MUST stay on-subject — do NOT produce questions from other subjects)\n"
                f"GRADE LEVEL: Grade {class_grade}\n"
                f"STANDARDS TO COVER:\n" + "\n".join(
                    f"  - {d['code']}: {d['description']}" for d in standard_details
                ) +
                f"\n\nEvery question MUST be about {class_subject} content at the Grade {class_grade} level, "
                f"directly aligned to at least one of the listed standards above."
            )
            log.info(f"[Games] Standards-fallback prompt for class_id={class_id}:\n{topic_from_standards[:500]}")
            from src.lms_agents.tools.question_generator import generate_questions
            gen_result = generate_questions(
                topic=topic_from_standards,
                grade=class_grade, subject=class_subject,
                count=count, standard_codes=standards,
            )
            if not gen_result.get("success"):
                grant_credits(teacher_id, cost, reason="Refund: Haiku gen failed", bucket="purchased")
                return {"error": gen_result.get("error", "Question generation failed")}
            raw_questions = [
                {
                    "question_number": i + 1,
                    "question_text": q["question"],
                    "answer": q["answer"],
                    "distractors": q.get("distractors", []),
                    "standard_code": q.get("standard_code") or (standards[i % len(standards)] if standards else ""),
                }
                for i, q in enumerate(gen_result["questions"])
            ]
            generated_questions_cache = raw_questions  # Replay stays free
            title = f"{class_subject} — {', '.join(standards[:3])}{'...' if len(standards) > 3 else ''}"

    elif source_type == "curriculum":
        calendar_id = question_source.get("calendar_id")
        unit_name = question_source.get("unit_name", "")
        unit_topic = question_source.get("topic", "")
        unit_standards = question_source.get("standards") or []
        count = question_source.get("question_count", 15)
        if not calendar_id and not unit_topic:
            return {"error": "calendar_id or topic required for type='curriculum'"}

        # Look up the class context
        class_grade, class_subject = _class_grade_subject(class_id)
        # Enriched standards descriptions
        standard_details = _fetch_standard_descriptions(unit_standards) if unit_standards else []

        # Prefer existing teacher assignments tagged to this unit's standards — free
        if unit_standards:
            raw_questions, matched_assignment_ids = _load_from_standards(teacher_id, unit_standards, count)
            if raw_questions:
                title = f"{unit_name or 'Unit'}: {unit_topic}".strip(': ')
                if len(set(matched_assignment_ids)) == 1:
                    assignment_id_for_row = matched_assignment_ids[0]
                # Done — skip Haiku path
                # Fall through to formatting
            else:
                raw_questions = None
        else:
            raw_questions = None

        if not raw_questions:
            # Charge credits and Haiku-generate from unit topic + standards
            from src.lms_agents.tools.credit_manager import charge_credits, grant_credits
            from src.lms_agents.config.pricing import CREDIT_COSTS
            cost = CREDIT_COSTS.get("live_game_custom_questions", 2)
            charge = charge_credits(
                teacher_id, cost,
                reference_type="live_game_curriculum",
                description=f"Live Game from curriculum unit '{unit_name}' ({count} questions)",
            )
            if not charge["success"]:
                return {
                    "error": charge.get("error", "Credit charge failed"),
                    "reason": "insufficient_credits",
                    **charge,
                }
            standards_section = ""
            if standard_details:
                standards_section = "\nSTANDARDS TO COVER:\n" + "\n".join(
                    f"  - {d['code']}: {d['description']}" for d in standard_details
                )
            topic_from_unit = (
                f"SUBJECT: {class_subject} (MUST stay on-subject — do NOT produce questions from other subjects)\n"
                f"GRADE LEVEL: Grade {class_grade}\n"
                f"UNIT: {unit_name or 'Untitled Unit'}\n"
                f"UNIT TOPIC: {unit_topic or '(not specified)'}"
                f"{standards_section}\n\n"
                f"Every question MUST be about {class_subject} content at the Grade {class_grade} level, "
                f"directly tied to the unit topic above."
            )
            log.info(f"[Games] Curriculum prompt for class_id={class_id}, unit={unit_name}:\n{topic_from_unit[:500]}")
            from src.lms_agents.tools.question_generator import generate_questions
            gen_result = generate_questions(
                topic=topic_from_unit,
                grade=class_grade, subject=class_subject,
                count=count, standard_codes=unit_standards,
            )
            if not gen_result.get("success"):
                grant_credits(teacher_id, cost, reason="Refund: Haiku gen failed", bucket="purchased")
                return {"error": gen_result.get("error", "Question generation failed")}
            raw_questions = [
                {
                    "question_number": i + 1,
                    "question_text": q["question"],
                    "answer": q["answer"],
                    "distractors": q.get("distractors", []),
                    "standard_code": q.get("standard_code") or (unit_standards[i % len(unit_standards)] if unit_standards else ""),
                }
                for i, q in enumerate(gen_result["questions"])
            ]
            generated_questions_cache = raw_questions
            title = f"{class_subject} — {unit_name}: {unit_topic}".strip(': ')

    elif source_type == "custom":
        prompt = question_source.get("prompt", "").strip()
        count = question_source.get("question_count", 15)
        if not prompt:
            return {"error": "prompt required for type='custom'"}
        # Charge credits BEFORE calling Haiku (atomic)
        from src.lms_agents.tools.credit_manager import charge_credits
        from src.lms_agents.config.pricing import CREDIT_COSTS
        cost = CREDIT_COSTS.get("live_game_custom_questions", 2)
        charge = charge_credits(
            teacher_id, cost,
            reference_type="live_game_custom",
            description=f"Live Game custom questions ({count} questions)",
        )
        if not charge["success"]:
            return {
                "error": charge.get("error", "Credit charge failed"),
                "reason": "insufficient_credits",
                **charge,
            }
        # Generate via Haiku — use the class's actual grade/subject
        class_grade, class_subject = _class_grade_subject(class_id)
        from src.lms_agents.tools.question_generator import generate_questions
        gen_result = generate_questions(
            topic=prompt, grade=class_grade, subject=class_subject, count=count,
        )
        if not gen_result.get("success"):
            # Refund on failure
            from src.lms_agents.tools.credit_manager import grant_credits
            grant_credits(teacher_id, cost, reason="Refund: Haiku question gen failed", bucket="purchased")
            return {"error": gen_result.get("error", "Question generation failed")}
        raw_questions = [
            {
                "question_number": i + 1,
                "question_text": q["question"],
                "answer": q["answer"],
                "distractors": q.get("distractors", []),
                "standard_code": q.get("standard_code", ""),
            }
            for i, q in enumerate(gen_result["questions"])
        ]
        generated_questions_cache = raw_questions  # Save for replay
        title = f"Custom: {prompt[:60]}"

    elif source_type == "cached":
        raw_questions = question_source.get("cached_questions") or []
        if not raw_questions:
            return {"error": "Replay source has no cached questions"}
        title = "Replay Game"
        generated_questions_cache = raw_questions  # Keep cache so another replay works

    else:
        return {"error": f"Unknown question_source.type: {source_type}"}

    # Generate unique PIN + session
    pin = _generate_pin()
    session_id = str(uuid4())

    # Filter malformed / fragment questions before formatting
    clean_questions = [q for q in raw_questions if _is_valid_question(q)]
    if not clean_questions:
        return {"error": "All generated questions were malformed — try a broader topic."}
    # Format questions for game shells (build MCQ options using REAL distractors)
    game_questions = [_format_question(i, q) for i, q in enumerate(clean_questions)]

    # Persist settings_json — cache generated questions if any so Replay is free
    settings_json = dict(settings or {})
    settings_json.setdefault("timer_seconds", 20)
    settings_json.setdefault("points_decay", True)
    if generated_questions_cache is not None:
        settings_json["generated_questions"] = generated_questions_cache
    if is_replay:
        settings_json["is_replay"] = True

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO game_sessions_v2
           (session_id, teacher_id, assignment_id, game_shell_id, pin, status, settings_json)
           VALUES (%s, %s::uuid, %s, %s, %s, 'lobby', %s)""",
        (session_id, teacher_id,
         assignment_id_for_row if assignment_id_for_row else None,
         game_shell_id, pin, Json(settings_json)),
    )
    conn.commit(); cur.close(); conn.close()

    # Store live state in Redis
    game_state = {
        "session_id": session_id,
        "pin": pin,
        "game_shell_id": game_shell_id,
        "title": title,
        "status": "lobby",
        "players": [],
        "questions": game_questions,
        "current_question": -1,
        "settings": settings_json,
    }
    set_game_state(pin, game_state)

    log.info(f"[Game] Created {pin} ({game_shell_id}) source={source_type} qs={len(game_questions)} replay={is_replay}")

    return {
        "session_id": session_id,
        "pin": pin,
        "game_shell_id": game_shell_id,
        "game_name": GAME_SHELLS[game_shell_id]["name"],
        "title": title,
        "question_count": len(game_questions),
        "status": "lobby",
        "is_replay": is_replay,
    }


def _load_assignment(assignment_id: str) -> tuple[list, str]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT title, questions FROM assignments WHERE assignment_id = %s", (assignment_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        return [], ""
    questions = row["questions"] if isinstance(row["questions"], list) else []
    return questions, row["title"] or "Live Game"


def _class_grade_subject(class_id: str | None) -> tuple[str, str]:
    """Fetch the class's grade_level and subject for Haiku context. Defaults: 5 / General."""
    if not class_id:
        return "5", "General"
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT grade_level, subject FROM classes WHERE class_id = %s::uuid", (class_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row:
            return str(row[0] or "5"), str(row[1] or "General")
    except Exception as e:
        log.warning(f"[Games] class lookup failed for {class_id}: {e}")
    return "5", "General"


def _fetch_standard_descriptions(codes: list[str]) -> list[dict]:
    """Look up descriptions for standard codes so Haiku knows what they mean."""
    if not codes:
        return []
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT code, description FROM standards WHERE code = ANY(%s) LIMIT 50",
            (codes,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        # Preserve the original order and fill missing codes with a placeholder
        by_code = {r["code"]: r["description"] for r in rows}
        return [{"code": c, "description": by_code.get(c, "(description not found)")} for c in codes]
    except Exception as e:
        log.warning(f"[Games] standards lookup failed: {e}")
        return [{"code": c, "description": ""} for c in codes]


def _load_from_standards(teacher_id: str, standards: list[str], count: int) -> tuple[list, list[str]]:
    """Merge questions from all teacher assignments that overlap with any standard in `standards`."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT assignment_id, questions
           FROM assignments
           WHERE teacher_id = %s::uuid
             AND (
               standards_ids::jsonb ?| %s
               OR EXISTS (
                 SELECT 1 FROM jsonb_array_elements_text(standards_ids::jsonb) AS s
                 WHERE s = ANY(%s)
               )
             )""",
        (teacher_id, standards, standards),
    )
    all_questions: list[dict] = []
    matched_assignments: list[str] = []
    for row in cur.fetchall():
        qs = row["questions"] if isinstance(row["questions"], list) else []
        for q in qs:
            if q.get("standard_code") in standards:
                all_questions.append(q)
                matched_assignments.append(str(row["assignment_id"]))
    cur.close(); conn.close()
    random.shuffle(all_questions)
    return all_questions[:count], matched_assignments


def _is_valid_question(q: dict) -> bool:
    """Filter out malformed Haiku output — incomplete stems, missing answer, or thin distractors."""
    stem = (q.get("question_text") or "").strip()
    answer = (q.get("answer") or "").strip()
    if len(stem) < 15 or not answer:
        return False
    # Stem shouldn't look like a fragment
    if stem.lower().startswith(("which shows", "which is", "which of")) and len(stem) < 25:
        return False
    return True


def _format_question(index: int, q: dict) -> dict:
    """Build the game-side question record with 4 shuffled MCQ options."""
    correct = q.get("answer", "")
    distractors = q.get("distractors") or []
    options = [correct] + list(distractors)[:3]
    # Pad with plausible placeholders if we're short — better than blanks
    while len(options) < 4:
        options.append(f"Option {len(options) + 1}")
    random.shuffle(options)
    return {
        "question_number": q.get("question_number", index + 1),
        "question_text": q.get("question_text", ""),
        "answer": correct,
        "options": options,
        "standard_code": q.get("standard_code", ""),
        "points": 1000,
    }


def join_game(pin: str, name: str, avatar: str = "🐻") -> dict:
    """Player joins a game session. Allows late-join during 'playing' state — the student
    is dropped into the current question so they can still participate."""
    state = get_game_state(pin)
    if not state:
        return {"error": "Game not found"}
    if state["status"] == "finished":
        return {"error": "Game already ended"}

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


def answer_question(pin: str, player_id: str, answer: str, time_taken: float = 0, wager: int | None = None) -> dict:
    """Player submits an answer.

    If `wager` is provided (int, can be 0), Jeopardy-style scoring applies:
      correct → +wager, wrong → -wager (score can go negative).
    Otherwise the standard decay-based scoring runs (Quiz Race, etc.).
    """
    state = get_game_state(pin)
    if not state:
        return {"error": "Game not found"}

    q_idx = state.get("current_question", 0)
    questions = state.get("questions", [])
    if q_idx >= len(questions):
        return {"error": "No current question"}

    question = questions[q_idx]
    correct = answer.strip().lower() == question["answer"].strip().lower()

    # Points calculation: wager-based (Jeopardy) or decay-based (everything else).
    if wager is not None:
        try:
            stake = max(0, int(wager))
        except (TypeError, ValueError):
            stake = 0
        points = stake if correct else -stake
    else:
        points = 0
        if correct:
            timer = state.get("settings", {}).get("timer_seconds", 20)
            points = max(100, int(1000 * (1 - time_taken / timer))) if state.get("settings", {}).get("points_decay") else 1000

    # Update player score in Redis. Score can go negative under Jeopardy scoring.
    new_score = 0
    for p in state.get("players", []):
        if p["player_id"] == player_id:
            p["score"] = p.get("score", 0) + points
            new_score = p["score"]
            p["answers"].append({
                "question": q_idx, "answer": answer, "correct": correct,
                "points": points, "time": time_taken, "wager": wager,
            })
            break
    set_game_state(pin, state)

    return {
        "correct": correct, "points": points,
        "correct_answer": question["answer"],
        "new_score": new_score,
        "wager": wager,
    }


def pick_question_by_index(pin: str, index: int) -> dict:
    """Teacher jumps to a specific question (Jeopardy cell pick)."""
    state = get_game_state(pin)
    if not state:
        return {"error": "Game not found"}
    questions = state.get("questions", [])
    if index < 0 or index >= len(questions):
        return {"error": "Invalid question index"}
    state["current_question"] = index
    set_game_state(pin, state)
    q = questions[index]
    return {
        "current_question": index,
        "total_questions": len(questions),
        "question": {
            "question_number": q["question_number"],
            "question_text": q["question_text"],
            "options": q["options"],
            "answer": q["answer"],  # teacher view sees answer
        },
    }


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
