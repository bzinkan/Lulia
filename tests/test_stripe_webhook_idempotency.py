"""
Stripe webhook idempotency regression test.

Why this exists:
    Stripe retries webhooks on any 5xx OR 2xx-timeout response (and also just
    randomly from time to time). If our handler isn't idempotent, a retried
    `payment_intent.succeeded` for a credit pack = a teacher who paid $10 gets
    $20 worth of credits, and the finance dashboard goes wrong.

    This test replays the same event twice and asserts the credit delta is
    applied exactly once. It's a regression test: any future refactor that
    accidentally breaks the `processed_webhooks` dedup gate will trip it.

Design:
    - Uses a deterministic event_id + fixed customer + fixed credit amount.
    - Bypasses the Stripe signature step by monkeypatching
      `construct_webhook_event` to return the payload as-is. We're testing
      our idempotency gate, not Stripe's signature crypto.
    - Records the teacher's `credit_balance` before/after each invocation
      and asserts second call is a no-op.
    - Cleans up the test rows in a finally block so the suite stays green
      on re-run.
"""
from __future__ import annotations

import os
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, "/app")
os.environ.setdefault("DB_HOST", "db")
os.environ.setdefault("DB_NAME", "lulia")


@pytest.fixture(scope="module")
def test_env():
    """Spin up a dedicated test teacher row + processed_webhooks row-cleanup."""
    from src.lms_agents.tools.db import get_connection
    teacher_id = str(uuid4())
    customer_id = f"cus_test_idempotency_{uuid4().hex[:10]}"
    event_id = f"evt_test_{uuid4().hex[:10]}"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO teachers
             (teacher_id, email, name, tier, credit_balance,
              stripe_customer_id, lifetime_credits_purchased)
           VALUES (%s::uuid, %s, %s, 'free', 25, %s, 0)""",
        (teacher_id, f"{teacher_id}@test.local", "Webhook Test", customer_id),
    )
    conn.commit()
    cur.close()
    conn.close()

    yield {
        "teacher_id": teacher_id,
        "customer_id": customer_id,
        "event_id": event_id,
    }

    # Cleanup — delete test rows so re-running the suite doesn't collide.
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM processed_webhooks WHERE event_id = %s", (event_id,))
    cur.execute("DELETE FROM credit_transactions_v2 WHERE teacher_id = %s::uuid", (teacher_id,))
    cur.execute("DELETE FROM teachers WHERE teacher_id = %s::uuid", (teacher_id,))
    conn.commit()
    cur.close()
    conn.close()


def _balance(teacher_id: str) -> tuple[int, int]:
    """(credit_balance, lifetime_credits_purchased) for a teacher."""
    from src.lms_agents.tools.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT credit_balance, lifetime_credits_purchased "
        "FROM teachers WHERE teacher_id = %s::uuid",
        (teacher_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return (row[0], row[1]) if row else (0, 0)


def test_webhook_replay_applies_credits_once(test_env, monkeypatch):
    """A retried Stripe webhook must not double-credit the teacher."""
    # Import AFTER env is set; avoids import-time side effects.
    from src.lms_agents.main import app
    from src.lms_agents.routers import stripe_webhooks as wh

    event = {
        "id": test_env["event_id"],
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "customer": test_env["customer_id"],
                "metadata": {"credits": "200"},
            }
        },
    }

    # Skip signature verification — not what we're testing here.
    monkeypatch.setattr(wh, "construct_webhook_event", lambda payload, sig: event)

    client = TestClient(app)

    before_bal, before_lifetime = _balance(test_env["teacher_id"])

    # First delivery — should grant 200 credits.
    r1 = client.post(
        "/api/v1/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "ignored"},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json().get("received") is True

    mid_bal, mid_lifetime = _balance(test_env["teacher_id"])
    assert mid_bal - before_bal == 200, (
        f"First delivery should grant 200 credits "
        f"(before={before_bal}, after={mid_bal})"
    )
    assert mid_lifetime - before_lifetime == 200

    # Second delivery of the same event_id — dedup gate should catch it.
    r2 = client.post(
        "/api/v1/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "ignored"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json().get("duplicate") is True, (
        f"Replay should be flagged duplicate, got {r2.json()}"
    )

    after_bal, after_lifetime = _balance(test_env["teacher_id"])
    assert after_bal == mid_bal, (
        f"Replay must not change credit_balance "
        f"(first={mid_bal}, replay={after_bal})"
    )
    assert after_lifetime == mid_lifetime, (
        "Replay must not change lifetime_credits_purchased"
    )
