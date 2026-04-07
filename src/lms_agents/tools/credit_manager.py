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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(credit_balance, 0) FROM teachers WHERE teacher_id = %s", (teacher_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row[0] if row else 0


def check_credits(teacher_id: str, cost: int) -> dict:
    """Check if teacher has enough credits. Returns {sufficient, balance, cost}."""
    balance = get_balance(teacher_id)
    # Max tier gets unlimited
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(tier, 'free') FROM teachers WHERE teacher_id = %s", (teacher_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    tier = row[0] if row else "free"

    if TIERS.get(tier, {}).get("credits_per_month", 0) == -1:
        return {"sufficient": True, "balance": balance, "cost": cost, "unlimited": True}

    return {"sufficient": balance >= cost, "balance": balance, "cost": cost, "unlimited": False}


def charge_credits(
    teacher_id: str,
    cost: int,
    reference_type: str = "",
    reference_id: str = "",
    description: str = "",
) -> dict:
    """
    Atomically charge credits. Uses SELECT FOR UPDATE to prevent race conditions.
    Returns {success, balance_after, transaction_id} or {success: False, error}.
    """
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Lock the row and get current balance
        cur.execute(
            "SELECT credit_balance, tier FROM teachers WHERE teacher_id = %s FOR UPDATE",
            (teacher_id,),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return {"success": False, "error": "Teacher not found"}

        balance, tier = row
        balance = balance or 0

        # Unlimited tier skips balance check
        if TIERS.get(tier, {}).get("credits_per_month", 0) != -1:
            if balance < cost:
                conn.rollback()
                return {"success": False, "error": "Insufficient credits", "balance": balance, "cost": cost}

        new_balance = balance - cost
        transaction_id = str(uuid4())

        cur.execute(
            "UPDATE teachers SET credit_balance = %s WHERE teacher_id = %s",
            (new_balance, teacher_id),
        )
        cur.execute(
            """INSERT INTO credit_transactions_v2
               (transaction_id, teacher_id, type, amount, balance_after,
                reference_type, reference_id, description)
               VALUES (%s, %s, 'generation_charge', %s, %s, %s, %s, %s)""",
            (transaction_id, teacher_id, -cost, new_balance,
             reference_type, reference_id, description),
        )
        conn.commit()
        log.info(f"[Credits] Charged {cost} from {teacher_id[:8]}, balance: {new_balance}")
        return {"success": True, "balance_after": new_balance, "transaction_id": transaction_id}

    except Exception as e:
        conn.rollback()
        log.error(f"[Credits] Charge failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        cur.close()
        conn.close()


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


def grant_credits(teacher_id: str, amount: int, reason: str = "", granted_by: str = "") -> dict:
    """Grant credits (signup bonus, manual admin grant, etc.)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teachers SET credit_balance = credit_balance + %s WHERE teacher_id = %s RETURNING credit_balance",
        (amount, teacher_id),
    )
    new_balance = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO credit_transactions_v2
           (transaction_id, teacher_id, type, amount, balance_after, description, metadata)
           VALUES (%s, %s, 'manual_grant', %s, %s, %s, %s)""",
        (str(uuid4()), teacher_id, amount, new_balance, reason, Json({"granted_by": granted_by})),
    )
    conn.commit()
    cur.close(); conn.close()
    return {"success": True, "balance_after": new_balance}


def estimate_cost(template_id: str, accommodation_count: int = 0) -> int:
    """Estimate credit cost for a generation."""
    base = get_credit_cost(template_id)
    return base + (accommodation_count * get_credit_cost("accommodation_version"))
