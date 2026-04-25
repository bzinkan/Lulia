"""Chat sidebar routes."""
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.chat_assistant import chat_message

router = APIRouter(prefix="/chat", tags=["Chat"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


class ChatRequest(BaseModel):
    message: str
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    session_id: Optional[str] = None
    context: Optional[dict] = None


@router.post("/message")
async def send_message(req: ChatRequest):
    """Send a chat message. Returns Claude's response + tool results."""
    result = chat_message(
        teacher_id=req.teacher_id,
        message=req.message,
        context=req.context,
        session_id=req.session_id,
    )
    return result


@router.get("/history")
async def get_history(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
    conn=Depends(get_db),
):
    """Get current chat session history."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM chat_sessions WHERE teacher_id = %s::uuid ORDER BY updated_at DESC LIMIT 1",
        (teacher_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return {"messages": [], "session_id": None}
    return {"messages": row.get("messages", []), "session_id": str(row["session_id"])}


@router.delete("/history")
async def clear_history(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
    conn=Depends(get_db),
):
    """Clear chat history."""
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_sessions WHERE teacher_id = %s::uuid", (teacher_id,))
    conn.commit()
    cur.close()
    return {"status": "cleared"}
