"""
Extended Admin API — moderation, support, features, announcements, billing.
All routes require X-Admin-Token header.
"""
import os
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.admin_auth import require_admin, log_admin_action
from src.lms_agents.tools.db import get_connection

router = APIRouter(prefix="/admin", tags=["Admin Extended"])


# ========== BILLING (mock data until Phase 15) ==========

@router.get("/billing/overview")
async def billing_overview(session=Depends(require_admin)):
    return {"mrr": 0, "active_subscriptions": {"basic": 1, "plus": 0, "premium": 0, "max": 0},
            "churn_rate": 0, "ltv_estimate": 0, "failed_payments": 0, "refunds_mtd": 0}

@router.get("/billing/transactions")
async def billing_transactions(session=Depends(require_admin)):
    return {"transactions": [], "total": 0}

@router.get("/billing/subscriptions")
async def billing_subscriptions(session=Depends(require_admin)):
    return {"subscriptions": [], "total": 0}

@router.get("/billing/credits")
async def billing_credits(session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT teacher_id, credits_remaining, tier FROM credit_accounts")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"credit_accounts": rows}


# ========== MODERATION ==========

@router.get("/moderation/queue")
async def moderation_queue(
    status: str = Query("pending"),
    session=Depends(require_admin),
):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM content_flags WHERE status = %s ORDER BY created_at ASC LIMIT 50",
        (status,),
    )
    flags = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"flags": flags, "total": len(flags)}


@router.get("/moderation/{flag_id}")
async def moderation_detail(flag_id: UUID, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM content_flags WHERE flag_id = %s", (str(flag_id),))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        return JSONResponse({"error": "Flag not found"}, status_code=404)
    return dict(row)


class ModerationAction(BaseModel):
    notes: str = ""

@router.post("/moderation/{flag_id}/dismiss")
async def dismiss_flag(flag_id: UUID, req: ModerationAction, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE content_flags SET status = 'dismissed', reviewed_by = %s, reviewed_at = NOW(), action_taken = 'dismissed' WHERE flag_id = %s",
        (session["email"], str(flag_id)),
    )
    conn.commit(); cur.close(); conn.close()
    log_admin_action(session["email"], "moderation_dismiss", "flag", str(flag_id))
    return {"status": "dismissed"}

@router.post("/moderation/{flag_id}/remove")
async def remove_flagged(flag_id: UUID, req: ModerationAction, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE content_flags SET status = 'removed', reviewed_by = %s, reviewed_at = NOW(), action_taken = 'removed' WHERE flag_id = %s",
        (session["email"], str(flag_id)),
    )
    conn.commit(); cur.close(); conn.close()
    log_admin_action(session["email"], "moderation_remove", "flag", str(flag_id))
    return {"status": "removed"}

@router.post("/moderation/{flag_id}/warn")
async def warn_teacher(flag_id: UUID, req: ModerationAction, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE content_flags SET status = 'reviewed', reviewed_by = %s, reviewed_at = NOW(), action_taken = 'warned' WHERE flag_id = %s",
        (session["email"], str(flag_id)),
    )
    conn.commit(); cur.close(); conn.close()
    log_admin_action(session["email"], "moderation_warn", "flag", str(flag_id), {"notes": req.notes})
    return {"status": "warned"}


# ========== SUPPORT ==========

@router.get("/support/tickets")
async def admin_tickets(
    status: Optional[str] = Query(None),
    session=Depends(require_admin),
):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if status:
        cur.execute(
            "SELECT st.*, t.name as teacher_name, t.email as teacher_email FROM support_tickets st LEFT JOIN teachers t ON st.teacher_id = t.teacher_id WHERE st.status = %s ORDER BY CASE st.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, st.created_at ASC LIMIT 50",
            (status,),
        )
    else:
        cur.execute(
            "SELECT st.*, t.name as teacher_name, t.email as teacher_email FROM support_tickets st LEFT JOIN teachers t ON st.teacher_id = t.teacher_id ORDER BY CASE st.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, st.created_at ASC LIMIT 50",
        )
    tickets = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"tickets": tickets}

@router.get("/support/tickets/{ticket_id}")
async def admin_ticket_detail(ticket_id: UUID, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT st.*, t.name as teacher_name FROM support_tickets st LEFT JOIN teachers t ON st.teacher_id = t.teacher_id WHERE ticket_id = %s", (str(ticket_id),))
    ticket = cur.fetchone()
    if not ticket:
        cur.close(); conn.close()
        return JSONResponse({"error": "Ticket not found"}, status_code=404)
    cur.execute("SELECT * FROM ticket_replies WHERE ticket_id = %s ORDER BY created_at", (str(ticket_id),))
    replies = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    result = dict(ticket)
    result["replies"] = replies
    return result

class TicketReplyRequest(BaseModel):
    message: str

@router.post("/support/tickets/{ticket_id}/reply")
async def admin_reply(ticket_id: UUID, req: TicketReplyRequest, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ticket_replies (reply_id, ticket_id, author_email, author_type, message) VALUES (%s, %s, %s, 'admin', %s)",
        (str(uuid4()), str(ticket_id), session["email"], req.message),
    )
    cur.execute("UPDATE support_tickets SET status = 'in_progress', updated_at = NOW() WHERE ticket_id = %s", (str(ticket_id),))
    conn.commit(); cur.close(); conn.close()
    return {"status": "replied"}

class TicketStatusRequest(BaseModel):
    status: str

@router.put("/support/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: UUID, req: TicketStatusRequest, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE support_tickets SET status = %s, updated_at = NOW() WHERE ticket_id = %s",
        (req.status, str(ticket_id)),
    )
    if req.status == 'resolved':
        cur.execute("UPDATE support_tickets SET resolved_at = NOW() WHERE ticket_id = %s", (str(ticket_id),))
    conn.commit(); cur.close(); conn.close()
    return {"status": req.status}


# ========== FEATURE FLAGS ==========

@router.get("/features")
async def list_features(session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM feature_flags ORDER BY name")
    flags = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"features": flags}

@router.get("/features/{key}")
async def feature_detail(key: str, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM feature_flags WHERE key = %s", (key,))
    flag = cur.fetchone()
    if not flag:
        cur.close(); conn.close()
        return JSONResponse({"error": "Feature not found"}, status_code=404)
    cur.execute("SELECT * FROM teacher_feature_overrides WHERE flag_key = %s", (key,))
    overrides = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    result = dict(flag)
    result["overrides"] = overrides
    return result

class FeatureUpdateRequest(BaseModel):
    default_enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = None
    tier_required: Optional[str] = None

@router.put("/features/{key}")
async def update_feature(key: str, req: FeatureUpdateRequest, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor()
    updates = []
    params = []
    if req.default_enabled is not None:
        updates.append("default_enabled = %s"); params.append(req.default_enabled)
    if req.rollout_percentage is not None:
        updates.append("rollout_percentage = %s"); params.append(req.rollout_percentage)
    if req.tier_required is not None:
        updates.append("tier_required = %s"); params.append(req.tier_required if req.tier_required else None)
    if updates:
        updates.append("updated_at = NOW()")
        params.append(key)
        cur.execute(f"UPDATE feature_flags SET {', '.join(updates)} WHERE key = %s", params)
    conn.commit(); cur.close(); conn.close()
    log_admin_action(session["email"], "feature_update", "feature_flag", key)
    return {"status": "updated"}

class FeatureOverrideRequest(BaseModel):
    teacher_id: str
    enabled: bool

@router.post("/features/{key}/override")
async def override_feature(key: str, req: FeatureOverrideRequest, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO teacher_feature_overrides (teacher_id, flag_key, enabled) VALUES (%s::uuid, %s, %s) ON CONFLICT (teacher_id, flag_key) DO UPDATE SET enabled = %s",
        (req.teacher_id, key, req.enabled, req.enabled),
    )
    conn.commit(); cur.close(); conn.close()
    return {"status": "overridden"}


# ========== ANNOUNCEMENTS ==========

@router.get("/announcements")
async def list_announcements(session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 50")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"announcements": rows}

class AnnouncementRequest(BaseModel):
    title: str
    message: str
    type: str = "info"
    audience: str = "all"
    delivery: str = "in_app"
    expires_at: Optional[str] = None

@router.post("/announcements")
async def create_announcement(req: AnnouncementRequest, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor()
    aid = str(uuid4())
    cur.execute(
        "INSERT INTO announcements (announcement_id, title, message, type, audience, delivery, created_by, expires_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (aid, req.title, req.message, req.type, req.audience, req.delivery, session["email"], req.expires_at),
    )
    conn.commit(); cur.close(); conn.close()
    log_admin_action(session["email"], "announcement_create", "announcement", aid)
    return {"announcement_id": aid, "status": "created"}

@router.delete("/announcements/{announcement_id}")
async def delete_announcement(announcement_id: UUID, session=Depends(require_admin)):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM announcement_dismissals WHERE announcement_id = %s", (str(announcement_id),))
    cur.execute("DELETE FROM announcements WHERE announcement_id = %s", (str(announcement_id),))
    conn.commit(); cur.close(); conn.close()
    return {"status": "deleted"}
