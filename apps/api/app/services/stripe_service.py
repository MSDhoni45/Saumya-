from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import stripe

from app.core.config import settings

logger = logging.getLogger(__name__)


def _client() -> stripe.StripeClient:
    if not settings.stripe_secret_key:
        raise ValueError("STRIPE_SECRET_KEY is not configured")
    return stripe.StripeClient(settings.stripe_secret_key)


def _price_id(plan: str) -> str:
    mapping: dict[str, str | None] = {
        "starter": settings.stripe_starter_price_id,
        "growth": settings.stripe_growth_price_id,
        "agency": settings.stripe_agency_price_id,
    }
    price_id = mapping.get(plan)
    if not price_id:
        raise ValueError(f"Stripe price ID for plan {plan!r} is not configured")
    return price_id


async def get_or_create_customer(*, email: str, name: str, business_id: str) -> str:
    def _sync() -> str:
        c = _client()
        results = c.customers.search({"query": f'metadata["business_id"]:"{business_id}"'})
        if results.data:
            return results.data[0].id
        customer = c.customers.create({
            "email": email,
            "name": name,
            "metadata": {"business_id": business_id},
        })
        return customer.id

    return await asyncio.to_thread(_sync)


async def create_checkout_session(
    *,
    business_id: str,
    plan: str,
    stripe_customer_id: str | None,
    customer_email: str,
    success_url: str,
    cancel_url: str,
) -> str:
    def _sync() -> str:
        c = _client()
        params: dict = {
            "mode": "subscription",
            "line_items": [{"price": _price_id(plan), "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"business_id": business_id, "plan": plan},
            "subscription_data": {"metadata": {"business_id": business_id, "plan": plan}},
        }
        if stripe_customer_id:
            params["customer"] = stripe_customer_id
        else:
            params["customer_email"] = customer_email
        session = c.checkout.sessions.create(params)
        return session.url

    return await asyncio.to_thread(_sync)


async def update_subscription_plan(stripe_subscription_id: str, new_plan: str) -> None:
    def _sync() -> None:
        c = _client()
        sub = c.subscriptions.retrieve(stripe_subscription_id)
        item_id = sub.items.data[0].id
        c.subscriptions.update(stripe_subscription_id, {
            "items": [{"id": item_id, "price": _price_id(new_plan)}],
            "proration_behavior": "create_prorations",
            "metadata": {"plan": new_plan},
        })

    await asyncio.to_thread(_sync)


async def cancel_at_period_end(stripe_subscription_id: str) -> None:
    def _sync() -> None:
        _client().subscriptions.update(stripe_subscription_id, {"cancel_at_period_end": True})

    await asyncio.to_thread(_sync)


async def reactivate(stripe_subscription_id: str) -> None:
    def _sync() -> None:
        _client().subscriptions.update(stripe_subscription_id, {"cancel_at_period_end": False})

    await asyncio.to_thread(_sync)


def parse_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    if not settings.stripe_webhook_secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET is not configured")
    return stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)


def ts_to_dt(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)
