"""
Credit Manager — atomic credit operations with transaction logging.

CRITICAL: charge_credits uses database transactions to prevent race conditions.
"""
import logging
from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection
from src.lms_agents.config.pricing import get_credit_cost, TIERS

log = logging.getLogger(__name__)


def get_balance(teacher_id: str) -> int:
    """Combined balance (monthly + purchased)."""
    b = get_balance_breakdown(teacher_id)
    return b["monthly"] + b["purchased"]


def get_balance_breakdown(teacher_id: str) -> dict:
    """Return {monthly, purchased, total}. Monthly resets each billing cycle; purchased never expires."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(credit_balance, 0), COALESCE(credits_purchased, 0) FROM teachers WHERE teacher_id = %s",
        (teacher_id,),
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    monthly = (row[0] if row else 0) or 0
    purchased = (row[1] if row else 0) or 0
    return {"monthly": monthly, "purchased": purchased, "total": monthly + purchased}


def check_credits(teacher_id: str, cost: int) -> dict:
    """Check if teacher has enough credits (monthly + purchased combined)."""
    b = get_balance_breakdown(teacher_id)
    total = b["total"]
    return {
        "sufficient": total >= cost,
        "balance": total,
        "monthly": b["monthly"],
        "purchased": b["purchased"],
        "cost": cost,
        "unlimited": False,
    }


def charge_credits(
    teacher_id: str,
    cost: int,
    reference_type: str = "",
    reference_id: str = "",
    description: str = "",
) -> dict:
    """
    Atomically charge credits with dual-bucket spend order: monthly first, then purchased.

    Monthly credits (credit_balance column) expire at the end of each billing cycle,
    so we spend them first to avoid wasting them. Purchased credits (credits_purchased
    column) never expire and roll over indefinitely.

    Uses SELECT FOR UPDATE to prevent race conditions.
    Returns {success, balance_after, monthly_used, purchased_used, transaction_id}.
    """
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute(
            """SELECT credit_balance, COALESCE(credits_purchased, 0), tier
               FROM teachers WHERE teacher_id = %s FOR UPDATE""",
            (teacher_id,),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return {"success": False, "error": "Teacher not found"}

        monthly, purchased, tier = row
        monthly = monthly or 0
        purchased = purchased or 0
        total = monthly + purchased

        if total < cost:
            conn.rollback()
            return {
                "success": False, "error": "Insufficient credits",
                "balance": total, "monthly": monthly, "purchased": purchased, "cost": cost,
            }

        # Spend monthly first, then purchased
        monthly_used = min(cost, monthly)
        purchased_used = cost - monthly_used
        new_monthly = monthly - monthly_used
        new_purchased = purchased - purchased_used
        new_total = new_monthly + new_purchased

        transaction_id = str(uuid4())

        cur.execute(
            "UPDATE teachers SET credit_balance = %s, credits_purchased = %s WHERE teacher_id = %s",
            (new_monthly, new_purchased, teacher_id),
        )
        cur.execute(
            """INSERT INTO credit_transactions_v2
               (transaction_id, teacher_id, type, amount, balance_after,
                reference_type, reference_id, description, metadata)
               VALUES (%s, %s, 'generation_charge', %s, %s, %s, %s, %s, %s)""",
            (transaction_id, teacher_id, -cost, new_total,
             reference_type, reference_id, description,
             Json({"monthly_used": monthly_used, "purchased_used": purchased_used})),
        )
        conn.commit()
        log.info(
            f"[Credits] Charged {cost} from {teacher_id[:8]} "
            f"({monthly_used} monthly + {purchased_used} purchased), total: {new_total}"
        )
        return {
            "success": True,
            "balance_after": new_total,
            "monthly_after": new_monthly,
            "purchased_after": new_purchased,
            "monthly_used": monthly_used,
            "purchased_used": purchased_used,
            "transaction_id": transaction_id,
        }

    except Exception as e:
        conn.rollback()
        log.error(f"[Credits] Charge failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        cur.close()
        conn.close()


def charge_for_clip(
    teacher_id: str,
    duration_sec: int,
    clip_id: str = "",
) -> dict:
    """
    Charge credits for a Short Clip generation.
    Uses CLIP_CREDITS_PER_SECOND from pricing config.
    Returns the same shape as charge_credits().
    """
    from src.lms_agents.config.pricing import CLIP_CREDITS_PER_SECOND
    cost = duration_sec * CLIP_CREDITS_PER_SECOND
    return charge_credits(
        teacher_id=teacher_id,
        cost=cost,
        reference_type="short_clip",
        reference_id=clip_id,
        description=f"Short clip generation ({duration_sec} sec)",
    )


def refund_credits(teacher_id: str, original_transaction_id: str, reason: str = "") -> dict:
    """Reverse a credit charge."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get original transaction
    cur.execute(
        "SELECT amount FROM credit_transactions_v2 WHERE transaction_id = %s",
        (original_transaction_id,),
    )
    orig = cur.fetchone()
    if not orig:
        cur.close(); conn.close()
        return {"success": False, "error": "Transaction not found"}

    refund_amount = abs(orig["amount"])  # Original was negative

    cur2 = conn.cursor()
    cur2.execute("UPDATE teachers SET credit_balance = credit_balance + %s WHERE teacher_id = %s RETURNING credit_balance", (refund_amount, teacher_id))
    new_balance = cur2.fetchone()[0]

    cur2.execute(
        """INSERT INTO credit_transactions_v2
           (transaction_id, teacher_id, type, amount, balance_after, reference_id, description)
           VALUES (%s, %s, 'refund', %s, %s, %s, %s)""",
        (str(uuid4()), teacher_id, refund_amount, new_balance, original_transaction_id, reason),
    )
    conn.commit()
    cur.close(); cur2.close(); conn.close()
    return {"success": True, "refunded": refund_amount, "balance_after": new_balance}


def grant_credits(
    teacher_id: str,
    amount: int,
    reason: str = "",
    granted_by: str = "",
    bucket: str = "monthly",
) -> dict:
    """
    Grant credits.

    bucket="monthly" — adds to subscription balance (resets on billing cycle).
                       Used for: signup bonuses, subscription renewal, admin grants.
    bucket="purchased" — adds to purchased balance (never expires).
                         Used for: Stripe credit-pack purchases.
    """
    column = "credit_balance" if bucket == "monthly" else "credits_purchased"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"""UPDATE teachers SET {column} = COALESCE({column}, 0) + %s
            WHERE teacher_id = %s RETURNING credit_balance, COALESCE(credits_purchased, 0)""",
        (amount, teacher_id),
    )
    row = cur.fetchone()
    monthly_after = row[0] or 0
    purchased_after = row[1] or 0
    total_after = monthly_after + purchased_after

    txn_type = "pack_purchase" if bucket == "purchased" else "manual_grant"
    cur.execute(
        """INSERT INTO credit_transactions_v2
           (transaction_id, teacher_id, type, amount, balance_after, description, metadata)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (str(uuid4()), teacher_id, txn_type, amount, total_after, reason,
         Json({"granted_by": granted_by, "bucket": bucket})),
    )
    conn.commit()
    cur.close(); conn.close()
    log.info(f"[Credits] Granted {amount} to {bucket} bucket for {teacher_id[:8]}, total: {total_after}")
    return {
        "success": True,
        "balance_after": total_after,
        "monthly_after": monthly_after,
        "purchased_after": purchased_after,
    }


def estimate_cost(template_id: str, accommodation_count: int = 0) -> int:
    """Estimate credit cost for a generation."""
    base = get_credit_cost(template_id)
    return base + (accommodation_count * get_credit_cost("accommodation_version"))
