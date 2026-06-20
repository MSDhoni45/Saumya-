from __future__ import annotations

import logging
import uuid

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.billing import Subscription
from app.services import billing_service, stripe_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/stripe", tags=["webhooks"])


@router.post("", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
) -> dict[str, str]:
    """Receive Stripe billing events (subscription lifecycle + payment status).

    Always returns 200 — Stripe retries aggressively on non-2xx responses so
    signature/parse failures are the only case where we raise a 400.
    """
    if not settings.billing_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is disabled",
        )
    raw_body = await request.body()

    try:
        event = stripe_service.parse_webhook_event(raw_body, stripe_signature or "")
    except (stripe.SignatureVerificationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    async with async_session_factory() as session:
        try:
            await _dispatch(session, event)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Error processing Stripe webhook event %s type=%s", event.id, event.type)

    return {"status": "received"}


async def _dispatch(session, event: stripe.Event) -> None:  # noqa: ANN001
    data = event.data.object
    t = event.type

    if t == "checkout.session.completed":
        await _on_checkout_completed(session, event, data)
    elif t == "customer.subscription.updated":
        await _on_subscription_updated(session, event, data)
    elif t == "customer.subscription.deleted":
        await _on_subscription_deleted(session, event, data)
    elif t == "invoice.payment_succeeded":
        await _on_payment_succeeded(session, event, data)
    elif t == "invoice.payment_failed":
        await _on_payment_failed(session, event, data)


async def _on_checkout_completed(session, event, data) -> None:
    meta = data.get("metadata") or {}
    business_id_str = meta.get("business_id")
    plan = meta.get("plan")
    if not business_id_str or not plan:
        return

    bid = uuid.UUID(business_id_str)
    await billing_service.activate_subscription(
        session,
        business_id=bid,
        plan=plan,
        provider="stripe",
        stripe_customer_id=data.get("customer"),
        stripe_subscription_id=data.get("subscription"),
    )
    await billing_service.record_billing_event(
        session,
        business_id=bid,
        event_type="checkout_completed",
        provider="stripe",
        provider_event_id=event.id,
        payload={"plan": plan, "stripe_subscription_id": data.get("subscription")},
    )


async def _on_subscription_updated(session, event, data) -> None:
    meta = data.get("metadata") or {}
    business_id_str = meta.get("business_id")
    if not business_id_str:
        return

    bid = uuid.UUID(business_id_str)
    plan = meta.get("plan", "starter")

    sub = await billing_service.get_or_create_subscription(session, bid)
    sub.plan = plan
    sub.status = _map_stripe_status(data.get("status", "active"))
    sub.cancel_at_period_end = data.get("cancel_at_period_end", False)
    sub.current_period_start = stripe_service.ts_to_dt(data.get("current_period_start"))
    sub.current_period_end = stripe_service.ts_to_dt(data.get("current_period_end"))

    await billing_service.record_billing_event(
        session,
        business_id=bid,
        event_type="subscription_updated",
        provider="stripe",
        provider_event_id=event.id,
        payload={"plan": plan, "status": sub.status, "cancel_at_period_end": sub.cancel_at_period_end},
    )


async def _on_subscription_deleted(session, event, data) -> None:
    meta = data.get("metadata") or {}
    business_id_str = meta.get("business_id")
    if not business_id_str:
        return

    bid = uuid.UUID(business_id_str)
    sub = await billing_service.get_or_create_subscription(session, bid)
    sub.status = "cancelled"
    sub.plan = "free"
    sub.payment_provider = None
    sub.stripe_subscription_id = None

    await billing_service.record_billing_event(
        session,
        business_id=bid,
        event_type="subscription_cancelled",
        provider="stripe",
        provider_event_id=event.id,
        payload={},
    )


async def _on_payment_succeeded(session, event, data) -> None:
    customer_id = data.get("customer")
    if not customer_id:
        return
    sub = await session.scalar(select(Subscription).where(Subscription.stripe_customer_id == customer_id))
    if sub is None:
        return

    sub.status = "active"
    await billing_service.record_billing_event(
        session,
        business_id=sub.business_id,
        event_type="payment_succeeded",
        provider="stripe",
        provider_event_id=event.id,
        payload={"amount": data.get("amount_paid"), "currency": data.get("currency")},
    )


async def _on_payment_failed(session, event, data) -> None:
    customer_id = data.get("customer")
    if not customer_id:
        return
    sub = await session.scalar(select(Subscription).where(Subscription.stripe_customer_id == customer_id))
    if sub is None:
        return

    sub.status = "past_due"
    await billing_service.record_billing_event(
        session,
        business_id=sub.business_id,
        event_type="payment_failed",
        provider="stripe",
        provider_event_id=event.id,
        payload={"amount_due": data.get("amount_due"), "currency": data.get("currency")},
    )


def _map_stripe_status(stripe_status: str) -> str:
    return {
        "active": "active",
        "trialing": "trialing",
        "past_due": "past_due",
        "canceled": "cancelled",
        "unpaid": "past_due",
        "paused": "paused",
    }.get(stripe_status, "active")
