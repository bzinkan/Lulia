"""Stripe Webhook Handler — processes subscription and payment events."""
import logging
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from psycopg2.extras import Json

from src.lms_agents.tools.stripe_client import construct_webhook_event
from src.lms_agents.tools.credit_manager import grant_credits
from src.lms_agents.tools.db import get_connection
from src.lms_agents.config.pricing import TIERS, CREDIT_PACKS

log = logging.getLogger(__name__)

router = APIRouter(tags=["Stripe Webhooks"])


def _tier_from_price(price_id: str) -> str:
    """Map a Stripe price ID to a tier name."""
    import os
    for tier_name, config in TIERS.items():
        env_key = config.get("stripe_price_env", "")
        if env_key and os.environ.get(env_key) == price_id:
            return tier_name
    return "basic"


def _credits_from_price(price_id: str) -> int:
    """Map a Stripe credit pack price ID to credit amount."""
    import os
    for pack in CREDIT_PACKS:
        if os.environ.get(pack.get("stripe_price_env", "")) == price_id:
            return pack["credits"]
    return 0


@router.post("/api/v1/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Process Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    event = construct_webhook_event(payload, sig_header)
    if not event:
        return JSONResponse({"error": "Invalid signature"}, status_code=400)

    event_type = event.get("type", "")
    event_id = event.get("id")
    data = event.get("data", {}).get("object", {})

    log.info(f"[Stripe Webhook] {event_type} ({event_id})")

    # Idempotency guard: skip if this event was already processed.
    # Stripe retries webhooks on timeout or 5xx — this prevents double-grants.
    if event_id:
        try:
            conn_dedup = get_connection()
            cur_dedup = conn_dedup.cursor()
            cur_dedup.execute(
                "INSERT INTO processed_webhooks (event_id, event_type) "
                "VALUES (%s, %s) ON CONFLICT (event_id) DO NOTHING RETURNING event_id",
                (event_id, event_type),
            )
            inserted = cur_dedup.fetchone()
            conn_dedup.commit()
            cur_dedup.close()
            conn_dedup.close()
            if not inserted:
                log.info(f"[Stripe Webhook] Duplicate event {event_id}, skipping")
                return {"received": True, "duplicate": True}
        except Exception as e:
            log.warning(f"[Stripe Webhook] Dedup check failed (proceeding anyway): {e}")

    try:
        if event_type == "customer.subscription.created":
            _handle_subscription_created(data)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data)
        elif event_type == "invoice.payment_succeeded":
            _handle_payment_succeeded(data)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(data)
        elif event_type == "payment_intent.succeeded":
            _handle_credit_purchase(data)
    except Exception as e:
        log.error(f"[Stripe Webhook] Error handling {event_type}: {e}")

    return {"received": True}


def _handle_subscription_created(sub):
    customer_id = sub.get("customer")
    price_id = sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
    tier = _tier_from_price(price_id)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE teachers SET tier = %s, stripe_subscription_id = %s,
           subscription_status = 'active', tier_started_at = NOW(),
           credit_balance = %s
           WHERE stripe_customer_id = %s""",
        (tier, sub.get("id"), TIERS.get(tier, {}).get("credits_per_month", 25), customer_id),
    )
    cur.execute(
        """INSERT INTO subscription_history (history_id, teacher_id, stripe_subscription_id, tier, action, amount_cents)
           SELECT %s, teacher_id, %s, %s, 'created', %s FROM teachers WHERE stripe_customer_id = %s""",
        (str(uuid4()), sub.get("id"), tier, TIERS.get(tier, {}).get("price_cents", 0), customer_id),
    )
    conn.commit(); cur.close(); conn.close()
    log.info(f"[Stripe] Subscription created: {customer_id} → {tier}")


def _handle_subscription_updated(sub):
    customer_id = sub.get("customer")
    price_id = sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
    new_tier = _tier_from_price(price_id)
    status = sub.get("status", "active")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT tier FROM teachers WHERE stripe_customer_id = %s", (customer_id,))
    row = cur.fetchone()
    old_tier = row[0] if row else "free"

    cur.execute(
        "UPDATE teachers SET tier = %s, subscription_status = %s WHERE stripe_customer_id = %s",
        (new_tier, status, customer_id),
    )

    if old_tier != new_tier:
        action = "upgraded" if TIERS.get(new_tier, {}).get("price_cents", 0) > TIERS.get(old_tier, {}).get("price_cents", 0) else "downgraded"
        cur.execute(
            """INSERT INTO subscription_history (history_id, teacher_id, stripe_subscription_id, tier, action, previous_tier, amount_cents)
               SELECT %s, teacher_id, %s, %s, %s, %s, %s FROM teachers WHERE stripe_customer_id = %s""",
            (str(uuid4()), sub.get("id"), new_tier, action, old_tier, TIERS.get(new_tier, {}).get("price_cents", 0), customer_id),
        )
    conn.commit(); cur.close(); conn.close()


def _handle_subscription_deleted(sub):
    customer_id = sub.get("customer")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teachers SET tier = 'free', subscription_status = 'canceled', credit_balance = 25 WHERE stripe_customer_id = %s",
        (customer_id,),
    )
    cur.execute(
        """INSERT INTO subscription_history (history_id, teacher_id, stripe_subscription_id, tier, action)
           SELECT %s, teacher_id, %s, 'free', 'canceled' FROM teachers WHERE stripe_customer_id = %s""",
        (str(uuid4()), sub.get("id"), customer_id),
    )
    conn.commit(); cur.close(); conn.close()
    log.info(f"[Stripe] Subscription canceled: {customer_id} → free")


def _handle_payment_succeeded(invoice):
    customer_id = invoice.get("customer")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO invoices (invoice_id, teacher_id, amount_cents, status, pdf_url, hosted_invoice_url, paid_at)
           SELECT %s, teacher_id, %s, 'paid', %s, %s, NOW() FROM teachers WHERE stripe_customer_id = %s
           ON CONFLICT (invoice_id) DO UPDATE SET status = 'paid', paid_at = NOW()""",
        (invoice.get("id"), invoice.get("amount_paid", 0), invoice.get("invoice_pdf"), invoice.get("hosted_invoice_url"), customer_id),
    )

    # Reset monthly credits on subscription renewal
    if invoice.get("billing_reason") in ("subscription_cycle", "subscription_create"):
        cur.execute("SELECT tier FROM teachers WHERE stripe_customer_id = %s", (customer_id,))
        row = cur.fetchone()
        if row:
            tier = row[0]
            monthly = TIERS.get(tier, {}).get("credits_per_month", 25)
            if monthly > 0:
                cur.execute("UPDATE teachers SET credit_balance = %s WHERE stripe_customer_id = %s", (monthly, customer_id))

    conn.commit(); cur.close(); conn.close()


def _handle_payment_failed(invoice):
    customer_id = invoice.get("customer")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teachers SET subscription_status = 'past_due' WHERE stripe_customer_id = %s",
        (customer_id,),
    )
    conn.commit(); cur.close(); conn.close()
    log.warning(f"[Stripe] Payment failed: {customer_id}")


def _handle_credit_purchase(payment_intent):
    """Handle one-time credit pack purchases."""
    customer_id = payment_intent.get("customer")
    # Credit amount stored in metadata during checkout
    credits = int(payment_intent.get("metadata", {}).get("credits", 0))
    if credits > 0 and customer_id:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT teacher_id FROM teachers WHERE stripe_customer_id = %s", (customer_id,))
        row = cur.fetchone()
        if row:
            grant_credits(str(row[0]), credits, f"Credit pack purchase: {credits} credits")
            cur.execute(
                "UPDATE teachers SET lifetime_credits_purchased = lifetime_credits_purchased + %s WHERE teacher_id = %s",
                (credits, str(row[0])),
            )
            conn.commit()
        cur.close(); conn.close()
