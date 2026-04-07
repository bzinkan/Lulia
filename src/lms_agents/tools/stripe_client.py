"""
Stripe Client — wrapper around the Stripe Python SDK.
"""
import logging
import os

import stripe

log = logging.getLogger(__name__)


def _init():
    stripe.api_key = os.environ.get("STRIPE_API_KEY", "")


def create_customer(email: str, name: str) -> str | None:
    _init()
    try:
        customer = stripe.Customer.create(email=email, name=name, metadata={"app": "lulia"})
        return customer.id
    except Exception as e:
        log.error(f"[Stripe] create_customer failed: {e}")
        return None


def create_checkout_session(customer_id: str, price_id: str, success_url: str, cancel_url: str, mode: str = "subscription") -> str | None:
    _init()
    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode=mode,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session.url
    except Exception as e:
        log.error(f"[Stripe] checkout session failed: {e}")
        return None


def create_portal_session(customer_id: str, return_url: str) -> str | None:
    _init()
    try:
        session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        return session.url
    except Exception as e:
        log.error(f"[Stripe] portal session failed: {e}")
        return None


def cancel_subscription(subscription_id: str, immediately: bool = False) -> bool:
    _init()
    try:
        if immediately:
            stripe.Subscription.cancel(subscription_id)
        else:
            stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        return True
    except Exception as e:
        log.error(f"[Stripe] cancel subscription failed: {e}")
        return False


def update_subscription(subscription_id: str, new_price_id: str) -> bool:
    _init()
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        stripe.Subscription.modify(
            subscription_id,
            items=[{"id": sub["items"]["data"][0].id, "price": new_price_id}],
            proration_behavior="create_prorations",
        )
        return True
    except Exception as e:
        log.error(f"[Stripe] update subscription failed: {e}")
        return False


def construct_webhook_event(payload: bytes, sig_header: str) -> dict | None:
    _init()
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        )
        return event
    except Exception as e:
        log.error(f"[Stripe] webhook verification failed: {e}")
        return None
