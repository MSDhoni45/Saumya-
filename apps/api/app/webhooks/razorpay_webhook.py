from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.billing import Subscription
from app.services import billing_service, razorpay_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/razorpay", tags=["webhooks"])


@router.post("", status_code=status.HTTP_200_OK)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(None, alias="X-Razorpay-Signature"),
) -> dict[str, str]:
    """Receive Razorpay subscription lifecycle and payment events."""
    raw_body = await request.body()

    if not x_razorpay_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Razorpay-Signature")

    try:
        valid = razorpay_service.verify_webhook_signature(raw_body, x_razorpay_signature)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except Exception:
        return {"status": "ignored"}

    event_type: str = payload.get("event", "")
    event_id: str = payload.get("id", "")

    async with async_session_factory() as session:
        try:
            await _dispatch(session, event_type, event_id, payload)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Error processing Razorpay webhook event %s type=%s", event_id, event_type)

    return {"status": "received"}


async def _dispatch(session, event_type: str, event_id: str, payload: dict) -> None:
    sub_data = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    if not sub_data:
        return

    notes = sub_data.get("notes") or {}
    business_id_str = notes.get("business_id") if isinstance(notes, dict) else None
    plan: str = (notes.get("plan", "starter") if isinstance(notes, dict) else "starter")
    razorpay_sub_id: str | None = sub_data.get("id")

    if not business_id_str:
        logger.warning("Razorpay webhook %s missing business_id in notes", event_id)
        return

    bid = uuid.UUID(business_id_str)

    if event_type == "subscription.activated":
        await billing_service.activate_subscription(
            session,
            business_id=bid,
            plan=plan,
            provider="razorpay",
            razorpay_subscription_id=razorpay_sub_id,
            current_period_start=razorpay_service.epoch_to_dt(sub_data.get("current_start")),
            current_period_end=razorpay_service.epoch_to_dt(sub_data.get("current_end")),
        )
        await billing_service.record_billing_event(
            session,
            business_id=bid,
            event_type="subscription_activated",
            provider="razorpay",
            provider_event_id=event_id,
            payload={"plan": plan, "razorpay_subscription_id": razorpay_sub_id},
        )

    elif event_type == "subscription.charged":
        sub = await session.scalar(
            select(Subscription).where(Subscription.razorpay_subscription_id == razorpay_sub_id)
        )
        if sub:
            sub.status = "active"
            sub.current_period_start = razorpay_service.epoch_to_dt(sub_data.get("current_start"))
            sub.current_period_end = razorpay_service.epoch_to_dt(sub_data.get("current_end"))
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        await billing_service.record_billing_event(
            session,
            business_id=bid,
            event_type="payment_succeeded",
            provider="razorpay",
            provider_event_id=event_id,
            payload={"amount": payment.get("amount"), "currency": payment.get("currency")},
        )

    elif event_type in ("subscription.cancelled", "subscription.completed"):
        sub = await session.scalar(
            select(Subscription).where(Subscription.razorpay_subscription_id == razorpay_sub_id)
        )
        if sub:
            sub.status = "cancelled"
            sub.plan = "free"
            sub.payment_provider = None
            sub.razorpay_subscription_id = None
        await billing_service.record_billing_event(
            session,
            business_id=bid,
            event_type="subscription_cancelled",
            provider="razorpay",
            provider_event_id=event_id,
            payload={"reason": event_type},
        )

    elif event_type == "subscription.halted":
        sub = await session.scalar(
            select(Subscription).where(Subscription.razorpay_subscription_id == razorpay_sub_id)
        )
        if sub:
            sub.status = "past_due"
        await billing_service.record_billing_event(
            session,
            business_id=bid,
            event_type="payment_failed",
            provider="razorpay",
            provider_event_id=event_id,
            payload={},
        )
