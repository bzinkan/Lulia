"""
Super Admin API — overview, teachers, activity, errors, costs, health, audit.
All routes require X-Admin-Token header from an authenticated super admin.
"""
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.admin_auth import (
    require_admin, is_super_admin, create_admin_session,
    log_admin_action, create_impersonation_token, end_impersonation,
)
from src.lms_agents.tools.db import get_connection

router = APIRouter(prefix="/admin", tags=["Admin"])


# --- Login (no admin token required) ---

class AdminLoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def admin_login(req: AdminLoginRequest):
    """Authenticate as super admin. Returns session token."""
    admin_pw = os.environ.get("ADMIN_PASSWORD", "admin")
    if not is_super_admin(req.email):
        return JSONResponse({"error": "Not a super admin"}, status_code=403)
    if req.password != admin_pw:
        return JSONResponse({"error": "Invalid password"}, status_code=401)
    token = create_admin_session(req.email)
    log_admin_action(req.email, "admin_login")
    return {"token": token, "email": req.email}


# --- Overview ---

@router.get("/overview")
async def overview(session=Depends(require_admin)):
    """Dashboard stats for admin overview."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    stats = {}
    # Teachers
    cur.execute("SELECT COUNT(*) as total FROM teachers")
    stats["total_teachers"] = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM teachers WHERE created_at > NOW() - INTERVAL '7 days'")
    stats["active_teachers_7d"] = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM teachers WHERE created_at > NOW() - INTERVAL '30 days'")
    stats["active_teachers_30d"] = cur.fetchone()["total"]

    # Generations
    cur.execute("SELECT COUNT(*) as total FROM assignments WHERE created_at > NOW() - INTERVAL '1 day'")
    stats["generations_today"] = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM assignments WHERE created_at > NOW() - INTERVAL '7 days'")
    stats["generations_this_week"] = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM assignments")
    stats["generations_total"] = cur.fetchone()["total"]

    # Plans
    cur.execute("SELECT COUNT(*) as total FROM lesson_plans WHERE created_at > NOW() - INTERVAL '7 days'")
    stats["plans_this_week"] = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM lesson_plans")
    stats["plans_total"] = cur.fetchone()["total"]

    # Errors
    cur.execute("SELECT COUNT(*) as total FROM system_errors WHERE created_at > NOW() - INTERVAL '1 day'")
    stats["errors_24h"] = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM system_errors WHERE created_at > NOW() - INTERVAL '7 days'")
    stats["errors_7d"] = cur.fetchone()["total"]

    # KB
    cur.execute("SELECT COUNT(*) as total FROM knowledge_sources")
    stats["kb_sources_total"] = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM knowledge_chunks")
    stats["kb_chunks_total"] = cur.fetchone()["total"]

    stats["revenue_mtd"] = 0  # Placeholder until Phase 15
    cur.close()
    conn.close()
    return stats


# --- Teachers ---

@router.get("/teachers")
async def list_teachers(
    search: Optional[str] = Query(None),
    sort: str = Query("recent"),
    limit: int = Query(50),
    offset: int = Query(0),
    session=Depends(require_admin),
):
    """List all teachers with search and pagination."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    conditions = []
    params = []
    if search:
        conditions.append("(name ILIKE %s OR email ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order = "ORDER BY created_at DESC" if sort == "recent" else "ORDER BY name ASC"

    cur.execute(
        f"""SELECT teacher_id, email, name, state_code, auth_provider,
                   dashboard_layout, design_theme, auto_plan_enabled,
                   created_at,
                   (SELECT COUNT(*) FROM assignments WHERE teacher_id = t.teacher_id) as total_generations,
                   (SELECT COUNT(*) FROM knowledge_sources WHERE teacher_id = t.teacher_id) as kb_sources
            FROM teachers t {where} {order} LIMIT %s OFFSET %s""",
        params + [limit, offset],
    )
    teachers = [dict(r) for r in cur.fetchall()]

    cur.execute(f"SELECT COUNT(*) as total FROM teachers t {where}", params)
    total = cur.fetchone()["total"]
    cur.close()
    conn.close()
    return {"teachers": teachers, "total": total}


@router.get("/teachers/{teacher_id}")
async def teacher_detail(teacher_id: UUID, session=Depends(require_admin)):
    """Detailed teacher view with usage stats."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    tid = str(teacher_id)

    cur.execute("SELECT * FROM teachers WHERE teacher_id = %s", (tid,))
    teacher = cur.fetchone()
    if not teacher:
        cur.close(); conn.close()
        return JSONResponse({"error": "Teacher not found"}, status_code=404)

    # Stats
    cur.execute("SELECT COUNT(*) as total FROM assignments WHERE teacher_id = %s", (tid,))
    gen_count = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM knowledge_sources WHERE teacher_id = %s", (tid,))
    kb_count = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM lesson_plans WHERE teacher_id = %s", (tid,))
    plan_count = cur.fetchone()["total"]

    # Classes
    cur.execute("SELECT * FROM classes WHERE teacher_id = %s ORDER BY name", (tid,))
    classes = [dict(r) for r in cur.fetchall()]

    # Recent assignments
    cur.execute(
        "SELECT assignment_id, title, output_template_id, status, created_at FROM assignments WHERE teacher_id = %s ORDER BY created_at DESC LIMIT 10",
        (tid,),
    )
    recent = [dict(r) for r in cur.fetchall()]

    cur.close(); conn.close()

    result = dict(teacher)
    result.pop("google_credentials_encrypted", None)  # Never expose
    result["stats"] = {"generations": gen_count, "kb_sources": kb_count, "plans": plan_count}
    result["classes"] = classes
    result["recent_assignments"] = recent
    return result


@router.post("/teachers/{teacher_id}/impersonate")
async def impersonate_teacher(teacher_id: UUID, session=Depends(require_admin)):
    """Create an impersonation token for viewing a teacher's dashboard."""
    token = create_impersonation_token(session["email"], str(teacher_id))
    log_admin_action(session["email"], "impersonate", "teacher", str(teacher_id))
    return {"impersonation_token": token, "teacher_id": str(teacher_id)}


@router.post("/impersonation/end")
async def stop_impersonation(token: str = Query(...), session=Depends(require_admin)):
    """End an impersonation session."""
    end_impersonation(token)
    return {"status": "ended"}


@router.post("/teachers/{teacher_id}/suspend")
async def suspend_teacher(teacher_id: UUID, session=Depends(require_admin)):
    """Suspend a teacher account."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teachers SET auth_provider = 'suspended' WHERE teacher_id = %s",
        (str(teacher_id),),
    )
    conn.commit(); cur.close(); conn.close()
    log_admin_action(session["email"], "suspend_teacher", "teacher", str(teacher_id))
    return {"status": "suspended"}


@router.post("/teachers/{teacher_id}/unsuspend")
async def unsuspend_teacher(teacher_id: UUID, session=Depends(require_admin)):
    """Restore a suspended teacher account."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teachers SET auth_provider = 'email' WHERE teacher_id = %s AND auth_provider = 'suspended'",
        (str(teacher_id),),
    )
    conn.commit(); cur.close(); conn.close()
    log_admin_action(session["email"], "unsuspend_teacher", "teacher", str(teacher_id))
    return {"status": "unsuspended"}


# --- Activity ---

@router.get("/activity")
async def activity_feed(limit: int = Query(100), session=Depends(require_admin)):
    """Recent activity across the system."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Combine recent assignments, plans, and uploads
    cur.execute("""
        (SELECT 'generation' as type, a.title as detail, a.teacher_id, a.created_at
         FROM assignments a ORDER BY created_at DESC LIMIT %s)
        UNION ALL
        (SELECT 'plan' as type, p.duration_type as detail, p.teacher_id, p.created_at
         FROM lesson_plans p ORDER BY created_at DESC LIMIT %s)
        UNION ALL
        (SELECT 'upload' as type, k.name as detail, k.teacher_id, k.uploaded_at as created_at
         FROM knowledge_sources k ORDER BY uploaded_at DESC LIMIT %s)
        ORDER BY created_at DESC LIMIT %s
    """, (limit, limit, limit, limit))
    items = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"activity": items}


# --- Errors ---

@router.get("/errors")
async def error_log(
    limit: int = Query(50),
    severity: Optional[str] = Query(None),
    session=Depends(require_admin),
):
    """Recent system errors."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    conditions = []
    params = []
    if severity:
        conditions.append("severity = %s")
        params.append(severity)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    cur.execute(
        f"SELECT * FROM system_errors {where} ORDER BY created_at DESC LIMIT %s",
        params,
    )
    errors = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"errors": errors}


# --- Costs ---

@router.get("/costs")
async def cost_estimate(session=Depends(require_admin)):
    """Estimated API costs for current month."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Count generations this month
    cur.execute("SELECT COUNT(*) as total FROM assignments WHERE created_at > date_trunc('month', NOW())")
    gen_count = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM knowledge_chunks WHERE embedding IS NOT NULL")
    embed_count = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM teachers")
    teacher_count = max(cur.fetchone()["total"], 1)
    cur.close(); conn.close()

    # Rough cost estimates
    anthropic_cost = gen_count * 0.08  # ~$0.08 per generation (4 calls × ~$0.02 per Sonnet call)
    gemini_cost = 0  # Slides/Forms not heavily used yet
    bedrock_cost = embed_count * 0.0001  # ~$0.0001 per embedding
    aws_infra = 150  # Fixed estimate
    total = anthropic_cost + gemini_cost + bedrock_cost + aws_infra

    return {
        "anthropic_cost_mtd": round(anthropic_cost, 2),
        "gemini_cost_mtd": round(gemini_cost, 2),
        "bedrock_cost_mtd": round(bedrock_cost, 2),
        "aws_infra_cost_mtd": aws_infra,
        "total_cost_mtd": round(total, 2),
        "cost_per_teacher": round(total / teacher_count, 2),
        "generations_mtd": gen_count,
        "embeddings_total": embed_count,
    }


# --- Health ---

@router.get("/health")
async def system_health(session=Depends(require_admin)):
    """System health check — database, storage, APIs."""
    health = {}

    # Database
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT pg_database_size('lulia') as db_size")
        health["database"] = {"status": "healthy", "size_bytes": cur.fetchone()["db_size"]}
        cur.execute("SELECT COUNT(*) as pending FROM events WHERE status = 'pending'")
        health["event_queue"] = {"pending": cur.fetchone()["pending"]}
        cur.close(); conn.close()
    except Exception as e:
        health["database"] = {"status": "error", "error": str(e)}

    # MinIO
    try:
        import boto3
        s3 = boto3.client(
            "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        buckets = s3.list_buckets()["Buckets"]
        health["storage"] = {"status": "healthy", "buckets": len(buckets)}
    except Exception as e:
        health["storage"] = {"status": "error", "error": str(e)}

    # Anthropic
    health["anthropic"] = {"status": "configured" if os.environ.get("ANTHROPIC_API_KEY") else "not_configured"}
    health["gemini"] = {"status": "configured" if os.environ.get("GOOGLE_GEMINI_API_KEY") else "not_configured"}
    health["bedrock"] = {"status": "configured" if os.environ.get("AWS_ACCESS_KEY_ID") else "not_configured"}

    # Failed jobs
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT COUNT(*) as total FROM system_errors WHERE created_at > NOW() - INTERVAL '1 day'")
        health["failed_jobs_24h"] = cur.fetchone()["total"]
        cur.close(); conn.close()
    except Exception:
        health["failed_jobs_24h"] = -1

    return health


# --- Audit ---

@router.get("/audit")
async def audit_log(limit: int = Query(100), session=Depends(require_admin)):
    """Admin audit log."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM admin_audit_log ORDER BY created_at DESC LIMIT %s",
        (limit,),
    )
    logs = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"audit_log": logs}
