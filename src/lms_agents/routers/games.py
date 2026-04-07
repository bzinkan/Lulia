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


class CreateGameRequest(BaseModel):
    assignment_id: str
    game_shell_id: str = "classic_quiz"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    settings: Optional[dict] = None


@router.get("/api/v1/games/shells")
async def list_game_shells():
    """List available game shell types."""
    shells = [{"id": sid, **info} for sid, info in GAME_SHELLS.items()]
    return {"shells": shells}


@router.post("/api/v1/games/create")
async def create_game(req: CreateGameRequest):
    """Create a new game session. Returns PIN."""
    result = create_game_session(
        teacher_id=req.teacher_id,
        assignment_id=req.assignment_id,
        game_shell_id=req.game_shell_id,
        settings=req.settings,
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
