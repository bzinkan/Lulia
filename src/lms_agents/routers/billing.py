"""Teacher-facing billing — plan info, credit balance, checkout, invoices."""
import os
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.stripe_client import create_customer, create_checkout_session, create_portal_session, cancel_subscription
from src.lms_agents.tools.credit_manager import get_balance, estimate_cost
from src.lms_agents.config.pricing import TIERS, CREDIT_PACKS, get_stripe_price_id
from src.lms_agents.tools.auth import require_teacher

router = APIRouter(prefix="/billing", tags=["Billing"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/me")
async def billing_status(
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Current billing status: tier, credits, subscription info."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT tier, credit_balance, subscription_status, stripe_subscription_id,
                  tier_started_at, lifetime_credits_purchased, lifetime_revenue_cents
           FROM teachers WHERE teacher_id = %s""",
        (teacher_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Teacher not found"}, status_code=404)

    tier = row.get("tier", "free")
    tier_config = TIERS.get(tier, TIERS["free"])

    return {
        **dict(row),
        "credits_per_month": tier_config["credits_per_month"],
        "max_classes": tier_config["max_classes"],
        "price_cents": tier_config["price_cents"],
    }


@router.get("/usage")
async def credit_usage(
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """This month's credit usage breakdown."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT reference_type, COUNT(*) as count, SUM(ABS(amount)) as credits_used
           FROM credit_transactions_v2
           WHERE teacher_id = %s::uuid AND type = 'generation_charge'
             AND created_at > date_trunc('month', NOW())
           GROUP BY reference_type ORDER BY credits_used DESC""",
        (teacher_id,),
    )
    usage = [dict(r) for r in cur.fetchall()]
    cur.close()
    total_used = sum(u["credits_used"] for u in usage)
    return {"usage": usage, "total_used": total_used}


@router.get("/transactions")
async def credit_transactions(
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Credit transaction history."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM credit_transactions_v2 WHERE teacher_id = %s::uuid ORDER BY created_at DESC LIMIT 50",
        (teacher_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"transactions": rows}


@router.get("/invoices")
async def list_invoices(
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Invoice history."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM invoices WHERE teacher_id = %s::uuid ORDER BY created_at DESC LIMIT 20",
        (teacher_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"invoices": rows}


@router.get("/credit-packs")
async def credit_packs():
    """Available credit packs for purchase."""
    return {"packs": CREDIT_PACKS}


@router.get("/estimate")
async def estimate(template_id: str = Query("worksheet"), accommodations: int = Query(0)):
    """Estimate credit cost before generation."""
    cost = estimate_cost(template_id, accommodations)
    return {"template_id": template_id, "cost": cost, "accommodations": accommodations}


class CheckoutRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    tier: Optional[str] = None
    pack_id: Optional[str] = None


@router.post("/checkout/subscription")
async def checkout_subscription(
    req: CheckoutRequest,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Create Stripe checkout session for subscription."""
    req.teacher_id = teacher_id
    if not req.tier or req.tier not in TIERS or req.tier == "free":
        return JSONResponse({"error": "Invalid tier"}, status_code=400)

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT stripe_customer_id, email, name FROM teachers WHERE teacher_id = %s", (req.teacher_id,))
    teacher = cur.fetchone()
    cur.close()
    if not teacher:
        return JSONResponse({"error": "Teacher not found"}, status_code=404)

    # Create Stripe customer if needed
    customer_id = teacher.get("stripe_customer_id")
    if not customer_id:
        customer_id = create_customer(teacher["email"], teacher["name"])
        if customer_id:
            cur2 = conn.cursor()
            cur2.execute("UPDATE teachers SET stripe_customer_id = %s WHERE teacher_id = %s", (customer_id, req.teacher_id))
            conn.commit(); cur2.close()

    price_env = TIERS[req.tier].get("stripe_price_env", "")
    price_id = get_stripe_price_id(price_env)
    if not price_id:
        return JSONResponse({"error": "Price not configured"}, status_code=500)

    dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:3001")
    url = create_checkout_session(
        customer_id, price_id,
        success_url=f"{dashboard_url}/billing/success?tier={req.tier}",
        cancel_url=f"{dashboard_url}/billing/canceled",
    )
    if not url:
        return JSONResponse({"error": "Could not create checkout session"}, status_code=500)
    return {"checkout_url": url}


@router.post("/checkout/credits")
async def checkout_credits(
    req: CheckoutRequest,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Create Stripe checkout session for credit pack purchase."""
    req.teacher_id = teacher_id
    pack = next((p for p in CREDIT_PACKS if p["id"] == req.pack_id), None)
    if not pack:
        return JSONResponse({"error": "Invalid pack"}, status_code=400)

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT stripe_customer_id, email, name FROM teachers WHERE teacher_id = %s", (req.teacher_id,))
    teacher = cur.fetchone()
    cur.close()

    if not teacher:
        return JSONResponse({"error": "Teacher not found"}, status_code=404)

    customer_id = teacher.get("stripe_customer_id")
    if not customer_id:
        customer_id = create_customer(teacher["email"], teacher["name"])
        if customer_id:
            cur2 = conn.cursor()
            cur2.execute("UPDATE teachers SET stripe_customer_id = %s WHERE teacher_id = %s", (customer_id, req.teacher_id))
            conn.commit(); cur2.close()

    price_id = get_stripe_price_id(pack.get("stripe_price_env", ""))
    if not price_id:
        return JSONResponse({"error": "Price not configured"}, status_code=500)

    dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:3001")
    url = create_checkout_session(
        customer_id, price_id,
        success_url=f"{dashboard_url}/billing/success?credits={pack['credits']}",
        cancel_url=f"{dashboard_url}/billing/canceled",
        mode="payment",
    )
    return {"checkout_url": url}


@router.post("/portal")
async def customer_portal(
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Create Stripe customer portal session."""
    cur = conn.cursor()
    cur.execute("SELECT stripe_customer_id FROM teachers WHERE teacher_id = %s", (teacher_id,))
    row = cur.fetchone()
    cur.close()
    if not row or not row[0]:
        return JSONResponse({"error": "No Stripe customer"}, status_code=400)

    dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:3001")
    url = create_portal_session(row[0], f"{dashboard_url}/billing")
    return {"portal_url": url}


@router.post("/cancel")
async def cancel(
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Cancel subscription at period end."""
    cur = conn.cursor()
    cur.execute("SELECT stripe_subscription_id FROM teachers WHERE teacher_id = %s", (teacher_id,))
    row = cur.fetchone()
    cur.close()
    if not row or not row[0]:
        return JSONResponse({"error": "No subscription"}, status_code=400)

    success = cancel_subscription(row[0])
    return {"status": "canceling" if success else "failed"}
