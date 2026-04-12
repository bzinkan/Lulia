"""Live Game routes — create sessions, manage gameplay, view results."""
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.game_session_manager import (
    create_game_session, join_game, start_game, end_game, GAME_SHELLS,
)
from src.lms_agents.tools.redis_client import get_game_state
from src.lms_agents.websocket.game_server import handle_game_websocket

router = APIRouter(tags=["Games"])


def get_db():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )
    try:
        yield conn
    finally:
        conn.close()


class QuestionSource(BaseModel):
    """Discriminated union for how a game gets its questions."""
    type: str  # 'assignment' | 'standards' | 'custom'
    assignment_id: Optional[str] = None
    standards: Optional[list[str]] = None
    prompt: Optional[str] = None
    question_count: int = 15


class CreateGameRequest(BaseModel):
    game_shell_id: str = "quiz_race"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    class_id: Optional[str] = None
    question_source: QuestionSource
    settings: Optional[dict] = None


class ReplayRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"


@router.get("/api/v1/games/shells")
async def list_game_shells():
    """List available game shell types."""
    shells = [{"id": sid, **info} for sid, info in GAME_SHELLS.items()]
    return {"shells": shells}


@router.post("/api/v1/games/create")
async def create_game(req: CreateGameRequest):
    """
    Create a new game session.
    Question source determines credit charging:
      - assignment: free
      - standards:  free (pulls from teacher's existing assignments tagged to those standards)
      - custom:     charges live_game_custom_questions credits (Haiku generation)
    """
    result = create_game_session(
        teacher_id=req.teacher_id,
        game_shell_id=req.game_shell_id,
        class_id=req.class_id,
        question_source=req.question_source.model_dump(),
        settings=req.settings,
    )
    if not result.get("success", True):
        return JSONResponse(result, status_code=402 if result.get("reason") == "insufficient_credits" else 400)
    return result


@router.post("/api/v1/games/{session_id}/replay")
async def replay_game(session_id: UUID, req: ReplayRequest, conn=Depends(get_db)):
    """
    Replay a prior session — same questions, same settings, new PIN.
    Never charges credits, even if the original was a custom-generated game.
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT game_shell_id, class_id, assignment_id, settings_json
           FROM game_sessions_v2 WHERE session_id = %s""",
        (str(session_id),),
    )
    prior = cur.fetchone()
    cur.close()
    if not prior:
        return JSONResponse({"error": "Original session not found"}, status_code=404)

    settings_json = prior["settings_json"] or {}
    cached_questions = settings_json.get("generated_questions")
    # Build a replay question source: use cached questions if present, else point at the same assignment
    if cached_questions:
        replay_source = {"type": "cached", "cached_questions": cached_questions, "question_count": len(cached_questions)}
    elif prior["assignment_id"]:
        replay_source = {"type": "assignment", "assignment_id": str(prior["assignment_id"])}
    else:
        return JSONResponse({"error": "Cannot replay — no cached questions and no assignment"}, status_code=400)

    result = create_game_session(
        teacher_id=req.teacher_id,
        game_shell_id=prior["game_shell_id"],
        class_id=str(prior["class_id"]) if prior["class_id"] else None,
        question_source=replay_source,
        settings=settings_json,
        is_replay=True,
    )
    return result


@router.get("/api/v1/games/{pin}/info")
async def game_info(pin: str):
    """Public endpoint — students check game status before joining."""
    state = get_game_state(pin)
    if not state:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    return {
        "pin": pin,
        "title": state.get("title", ""),
        "game_shell_id": state.get("game_shell_id"),
        "status": state.get("status"),
        "player_count": len(state.get("players", [])),
    }


@router.post("/api/v1/games/{pin}/start")
async def start_game_route(pin: str):
    """Teacher starts the game."""
    return start_game(pin)


@router.post("/api/v1/games/{pin}/end")
async def end_game_route(pin: str):
    """Teacher ends the game."""
    return end_game(pin)


@router.get("/api/v1/games/{session_id}/results")
async def game_results(session_id: UUID, conn=Depends(get_db)):
    """Post-game results and analytics."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM game_results WHERE session_id = %s", (str(session_id),))
    result = cur.fetchone()
    if not result:
        cur.close()
        return JSONResponse({"error": "Results not found"}, status_code=404)

    cur.execute(
        "SELECT name, avatar, final_score, rank, answers_json FROM game_players WHERE session_id = %s ORDER BY rank ASC",
        (str(session_id),),
    )
    players = [dict(r) for r in cur.fetchall()]
    cur.close()

    res = dict(result)
    res["players"] = players
    return res


@router.get("/api/v1/games/sessions")
async def list_sessions(
    teacher_id: Optional[str] = Query(None),
    conn=Depends(get_db),
):
    """List teacher's recent game sessions."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if teacher_id:
        cur.execute(
            "SELECT * FROM game_sessions_v2 WHERE teacher_id = %s::uuid ORDER BY created_at DESC LIMIT 20",
            (teacher_id,),
        )
    else:
        cur.execute("SELECT * FROM game_sessions_v2 ORDER BY created_at DESC LIMIT 20")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"sessions": rows}


# --- WebSocket endpoint ---

@router.websocket("/ws/games/{pin}")
async def websocket_game(websocket: WebSocket, pin: str):
    """WebSocket connection for live game."""
    await handle_game_websocket(websocket, pin)
