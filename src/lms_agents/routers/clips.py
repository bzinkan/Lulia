"""
Short Clips — Veo 3 Fast generation with dual-bucket credit charging.

Endpoints:
  GET  /clips/cost?duration_sec=X  — preview credit cost + balance impact
  GET  /clips/balance              — current credit breakdown
  POST /clips/generate             — atomic charge + generate (refunds on failure)
  GET  /clips                      — list teacher's previously generated clips
"""
import logging
import os
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.config.pricing import CLIP_CREDITS_PER_SECOND, TIERS
from src.lms_agents.tools.credit_manager import (
    charge_for_clip,
    check_credits,
    get_balance_breakdown,
    grant_credits,
)
from src.lms_agents.tools.veo_generator import generate_clip, estimate_cost_usd

log = logging.getLogger(__name__)

router = APIRouter(prefix="/clips", tags=["Short Clips"])


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


def _warning_band(duration_sec: int) -> dict:
    """Return the UX warning band for a given duration."""
    if duration_sec <= 15:
        return {"level": "green", "label": "Perfect for hooks and intros."}
    if duration_sec <= 45:
        return {"level": "green", "label": "The sweet spot for concept demos."}
    if duration_sec <= 90:
        return {"level": "yellow", "label": "Uses a significant chunk of your credits."}
    return {
        "level": "red",
        "label": "Long clip — uses a large portion of your credits. Confirm before generating.",
        "require_confirm": True,
    }


@router.get("/cost")
async def cost_preview(
    duration_sec: int = Query(..., ge=1, le=300),
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
):
    """
    Preview what a clip of this duration will cost the teacher.
    Used by the pre-generation modal to show credit math before they commit.
    """
    credits_needed = duration_sec * CLIP_CREDITS_PER_SECOND
    b = get_balance_breakdown(teacher_id)
    sufficient = b["total"] >= credits_needed

    # Simulate spend order (monthly first, then purchased) for the after-balance display
    monthly_used = min(credits_needed, b["monthly"]) if sufficient else 0
    purchased_used = credits_needed - monthly_used if sufficient else 0
    after_monthly = b["monthly"] - monthly_used if sufficient else b["monthly"]
    after_purchased = b["purchased"] - purchased_used if sufficient else b["purchased"]

    return {
        "duration_sec": duration_sec,
        "credits_needed": credits_needed,
        "rate_per_sec": CLIP_CREDITS_PER_SECOND,
        "balance": {
            "monthly": b["monthly"],
            "purchased": b["purchased"],
            "total": b["total"],
        },
        "after": {
            "monthly": after_monthly,
            "purchased": after_purchased,
            "total": after_monthly + after_purchased,
        } if sufficient else None,
        "sufficient": sufficient,
        "warning": _warning_band(duration_sec),
        "est_cost_usd": round(estimate_cost_usd(duration_sec), 2),  # internal viz, not shown to teacher
    }


@router.get("/balance")
async def clip_balance(teacher_id: str = Query("00000000-0000-0000-0000-000000000001")):
    """Current dual-bucket balance — for the Clips tab header chip."""
    b = get_balance_breakdown(teacher_id)
    return {
        "monthly": b["monthly"],
        "purchased": b["purchased"],
        "total": b["total"],
        "rate_per_sec": CLIP_CREDITS_PER_SECOND,
        "max_seconds_affordable": b["total"] // CLIP_CREDITS_PER_SECOND,
    }


class GenerateClipRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    class_id: Optional[str] = None
    prompt: str
    duration_sec: int
    aspect_ratio: str = "16:9"
    topic_label: Optional[str] = None  # Optional metadata for filing/search


@router.post("/generate")
async def generate(req: GenerateClipRequest, conn=Depends(get_db)):
    """
    Generate a short clip. Charges credits atomically BEFORE calling Veo.
    If Veo fails, credits are refunded.
    """
    if req.duration_sec < 1 or req.duration_sec > 300:
        return JSONResponse({"error": "duration_sec must be 1-300"}, status_code=400)

    # Gate by tier — Free/Basic can't generate clips
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT tier FROM teachers WHERE teacher_id = %s", (req.teacher_id,))
    row = cur.fetchone()
    tier = row["tier"] if row else "free"
    if tier in ("free", "basic"):
        cur.close()
        return JSONResponse({
            "error": "Short Clips are available on Plus tier and above.",
            "tier_required": "plus",
            "current_tier": tier,
        }, status_code=402)

    # Charge credits atomically
    clip_id = str(uuid4())
    charge = charge_for_clip(req.teacher_id, req.duration_sec, clip_id=clip_id)
    if not charge["success"]:
        cur.close()
        return JSONResponse({"error": charge.get("error", "Credit charge failed"), **charge}, status_code=402)

    log.info(f"[Clips] Charged {req.duration_sec * CLIP_CREDITS_PER_SECOND} credits for clip {clip_id}")

    # Call Veo
    result = generate_clip(
        prompt=req.prompt,
        duration_sec=req.duration_sec,
        aspect_ratio=req.aspect_ratio,
    )

    if not result.get("success"):
        # Refund on failure
        grant_credits(
            req.teacher_id,
            req.duration_sec * CLIP_CREDITS_PER_SECOND,
            reason=f"Refund: Veo generation failed for clip {clip_id}",
            bucket="purchased",  # refund goes to purchased so it doesn't silently expire
        )
        log.error(f"[Clips] Veo failed, refunded credits for {clip_id}: {result.get('error')}")
        cur.close()
        return JSONResponse({
            "error": "Video generation failed. Your credits have been refunded.",
            "details": result.get("error"),
        }, status_code=502)

    # Persist the clip
    cur.execute(
        """INSERT INTO short_clips
           (clip_id, teacher_id, class_id, prompt, topic_label, duration_sec,
            aspect_ratio, video_uris, primary_uri, segments, model, credits_charged)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            clip_id, req.teacher_id, req.class_id, req.prompt, req.topic_label,
            result["duration_sec"], req.aspect_ratio,
            result["video_uris"], result["primary_uri"], result["segments"],
            result["model"], req.duration_sec * CLIP_CREDITS_PER_SECOND,
        ),
    )
    conn.commit()
    cur.close()

    return {
        "clip_id": clip_id,
        "video_uris": result["video_uris"],
        "primary_uri": result["primary_uri"],
        "duration_sec": result["duration_sec"],
        "segments": result["segments"],
        "credits_charged": req.duration_sec * CLIP_CREDITS_PER_SECOND,
        "balance_after": charge["balance_after"],
    }


@router.get("")
async def list_clips(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
    class_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    conn=Depends(get_db),
):
    """List the teacher's generated clips, most recent first."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if class_id:
        cur.execute(
            """SELECT clip_id, class_id, prompt, topic_label, duration_sec,
                      primary_uri, segments, credits_charged, created_at
               FROM short_clips WHERE teacher_id = %s AND class_id = %s::uuid
               ORDER BY created_at DESC LIMIT %s""",
            (teacher_id, class_id, limit),
        )
    else:
        cur.execute(
            """SELECT clip_id, class_id, prompt, topic_label, duration_sec,
                      primary_uri, segments, credits_charged, created_at
               FROM short_clips WHERE teacher_id = %s
               ORDER BY created_at DESC LIMIT %s""",
            (teacher_id, limit),
        )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"clips": rows, "total": len(rows)}
