from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from datetime import datetime, timezone

import razorpay

from app.core.config import settings

logger = logging.getLogger(__name__)


def _client() -> razorpay.Client:
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise ValueError("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not configured")
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def _plan_id(plan: str) -> str:
    mapping: dict[str, str | None] = {
        "starter": settings.razorpay_starter_plan_id,
        "growth": settings.razorpay_growth_plan_id,
        "agency": settings.razorpay_agency_plan_id,
    }
    plan_id = mapping.get(plan)
    if not plan_id:
        raise ValueError(f"Razorpay plan ID for plan {plan!r} is not configured")
    return plan_id


async def create_customer(*, name: str, email: str, business_id: str) -> str:
    def _sync() -> str:
        return _client().customer.create({
            "name": name,
            "email": email,
            "notes": {"business_id": business_id},
        })["id"]

    return await asyncio.to_thread(_sync)


async def create_subscription(*, plan: str, business_id: str, customer_id: str | None) -> dict:
    def _sync() -> dict:
        data: dict = {
            "plan_id": _plan_id(plan),
            "total_count": 120,  # billing cycles cap (10 years)
            "quantity": 1,
            "notes": {"business_id": business_id, "plan": plan},
        }
        if customer_id:
            data["customer_id"] = customer_id
        return _client().subscription.create(data)

    return await asyncio.to_thread(_sync)


async def cancel_subscription(razorpay_subscription_id: str, *, at_cycle_end: bool = True) -> dict:
    def _sync() -> dict:
        return _client().subscription.cancel(
            razorpay_subscription_id,
            {"cancel_at_cycle_end": 1 if at_cycle_end else 0},
        )

    return await asyncio.to_thread(_sync)


async def fetch_subscription(razorpay_subscription_id: str) -> dict:
    def _sync() -> dict:
        return _client().subscription.fetch(razorpay_subscription_id)

    return await asyncio.to_thread(_sync)


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    if not settings.razorpay_webhook_secret:
        raise ValueError("RAZORPAY_WEBHOOK_SECRET is not configured")
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def epoch_to_dt(epoch: int | None) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc)
