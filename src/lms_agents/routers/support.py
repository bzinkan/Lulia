"""Teacher-facing support + announcements + feature flags + content flagging."""
import os
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.feature_flags import get_teacher_features

router = APIRouter(tags=["Support & Features"])


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


# --- Support Tickets ---

class CreateTicketRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    subject: str
    message: str
    category: str = "other"
    priority: str = "medium"

@router.post("/support/tickets")
async def create_ticket(req: CreateTicketRequest, conn=Depends(get_db)):
    cur = conn.cursor()
    tid = str(uuid4())
    cur.execute(
        "INSERT INTO support_tickets (ticket_id, teacher_id, subject, message, category, priority) VALUES (%s, %s::uuid, %s, %s, %s, %s)",
        (tid, req.teacher_id, req.subject, req.message, req.category, req.priority),
    )
    conn.commit(); cur.close()
    return {"ticket_id": tid, "status": "open"}

@router.get("/support/tickets/mine")
async def my_tickets(teacher_id: str = Query("00000000-0000-0000-0000-000000000001"), conn=Depends(get_db)):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM support_tickets WHERE teacher_id = %s::uuid ORDER BY created_at DESC", (teacher_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"tickets": rows}

class ReplyRequest(BaseModel):
    message: str
    teacher_email: str = "teacher@lulia.com"

@router.post("/support/tickets/{ticket_id}/reply")
async def reply_ticket(ticket_id: UUID, req: ReplyRequest, conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ticket_replies (reply_id, ticket_id, author_email, author_type, message) VALUES (%s, %s, %s, 'teacher', %s)",
        (str(uuid4()), str(ticket_id), req.teacher_email, req.message),
    )
    conn.commit(); cur.close()
    return {"status": "replied"}


# --- Announcements ---

@router.get("/announcements/active")
async def active_announcements(teacher_id: str = Query("00000000-0000-0000-0000-000000000001"), conn=Depends(get_db)):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT a.* FROM announcements a
           WHERE a.audience = 'all'
             AND (a.expires_at IS NULL OR a.expires_at > NOW())
             AND a.announcement_id NOT IN (SELECT announcement_id FROM announcement_dismissals WHERE teacher_id = %s::uuid)
           ORDER BY a.created_at DESC LIMIT 5""",
        (teacher_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"announcements": rows}

@router.post("/announcements/{announcement_id}/dismiss")
async def dismiss_announcement(announcement_id: UUID, teacher_id: str = Query("00000000-0000-0000-0000-000000000001"), conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO announcement_dismissals (teacher_id, announcement_id) VALUES (%s::uuid, %s) ON CONFLICT DO NOTHING",
        (teacher_id, str(announcement_id)),
    )
    conn.commit(); cur.close()
    return {"status": "dismissed"}


# --- Feature Flags ---

@router.get("/features/mine")
async def my_features(teacher_id: str = Query("00000000-0000-0000-0000-000000000001")):
    features = get_teacher_features(teacher_id)
    return {"features": features}


# --- Content Flagging ---

class FlagRequest(BaseModel):
    content_type: str  # assignment, video, interactive
    content_id: str
    reason: str  # inappropriate, factually_wrong, offensive, copyright
    description: str = ""
    teacher_id: str = "00000000-0000-0000-0000-000000000001"

@router.post("/flags")
async def flag_content(req: FlagRequest, conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO content_flags (flag_id, content_type, content_id, teacher_id, reason, description, flagged_by) VALUES (%s, %s, %s::uuid, %s::uuid, %s, %s, %s)",
        (str(uuid4()), req.content_type, req.content_id, req.teacher_id, req.reason, req.description, req.teacher_id),
    )
    conn.commit(); cur.close()
    return {"status": "flagged"}
