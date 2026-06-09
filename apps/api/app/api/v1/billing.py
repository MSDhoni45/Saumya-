from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BusinessContext, get_current_business, require_business_access
from app.core.config import settings
from app.core.plans import ORDERED_PLANS, get_plan
from app.db.session import get_db_session
from app.models.user import User
from app.models.whatsapp import Business
from app.schemas.billing import (
    CancelResponse,
    ChangePlanRequest,
    CheckoutRequest,
    PlanResponse,
    RazorpayCheckoutResponse,
    StripeCheckoutResponse,
    SubscriptionResponse,
    UsageResponse,
)
from app.services import billing_service, razorpay_service, stripe_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


def _default_success_url() -> str:
    base = settings.allowed_origins[0] if settings.allowed_origins else "http://localhost:3000"
    return f"{base}/settings/billing?success=true"


def _default_cancel_url() -> str:
    base = settings.allowed_origins[0] if settings.allowed_origins else "http://localhost:3000"
    return f"{base}/settings/billing?cancelled=true"


@router.get("/{business_id}/plans", response_model=list[PlanResponse])
async def list_plans(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[PlanResponse]:
    require_business_access(ctx, business_id)
    sub = await billing_service.get_or_create_subscription(session, business_id)
    await session.commit()
    return [
        PlanResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            message_limit=p.message_limit,
            price_usd_cents=p.price_usd_cents,
            price_inr_paise=p.price_inr_paise,
            is_current=(p.id == sub.plan),
        )
        for p in ORDERED_PLANS
    ]


@router.get("/{business_id}/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    require_business_access(ctx, business_id)
    sub = await billing_service.get_or_create_subscription(session, business_id)
    await session.commit()
    return SubscriptionResponse.model_validate(sub)


@router.get("/{business_id}/usage", response_model=UsageResponse)
async def get_usage(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> UsageResponse:
    require_business_access(ctx, business_id)
    sub = await billing_service.get_or_create_subscription(session, business_id)
    usage = await billing_service.get_current_usage(session, business_id)
    plan = get_plan(sub.plan)
    await session.commit()

    percent: float | None = None
    if plan.message_limit is not None and plan.message_limit > 0:
        percent = round(min(usage.message_count / plan.message_limit * 100, 100.0), 1)

    return UsageResponse(
        business_id=business_id,
        plan=sub.plan,
        message_limit=plan.message_limit,
        message_count=usage.message_count,
        period_start=usage.period_start,
        period_end=usage.period_end,
        percent_used=percent,
    )


@router.post("/{business_id}/checkout")
async def create_checkout(
    business_id: uuid.UUID,
    body: CheckoutRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a payment checkout session. Returns either a Stripe URL or Razorpay
    subscription details for the frontend to open the Razorpay widget."""
    require_business_access(ctx, business_id)

    business = await session.get(Business, business_id)
    user = await session.get(User, ctx.user_id)
    if not business or not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    sub = await billing_service.get_or_create_subscription(session, business_id)
    await session.commit()

    if body.provider == "stripe":
        if not settings.stripe_secret_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe is not configured on this server",
            )
        checkout_url = await stripe_service.create_checkout_session(
            business_id=str(business_id),
            plan=body.plan,
            stripe_customer_id=sub.stripe_customer_id,
            customer_email=user.email,
            success_url=body.success_url or _default_success_url(),
            cancel_url=body.cancel_url or _default_cancel_url(),
        )
        return StripeCheckoutResponse(checkout_url=checkout_url)

    # --- Razorpay ---
    if not settings.razorpay_key_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay is not configured on this server",
        )

    customer_id = sub.razorpay_customer_id
    if not customer_id:
        customer_id = await razorpay_service.create_customer(
            name=business.name,
            email=user.email,
            business_id=str(business_id),
        )
        sub.razorpay_customer_id = customer_id
        await session.commit()

    rp_sub = await razorpay_service.create_subscription(
        plan=body.plan,
        business_id=str(business_id),
        customer_id=customer_id,
    )
    plan_config = get_plan(body.plan)
    return RazorpayCheckoutResponse(
        razorpay_subscription_id=rp_sub["id"],
        razorpay_key_id=settings.razorpay_key_id,
        amount=plan_config.price_inr_paise,
        business_name=business.name,
    )


@router.post("/{business_id}/change-plan", response_model=SubscriptionResponse)
async def change_plan(
    business_id: uuid.UUID,
    body: ChangePlanRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Upgrade or downgrade to a different paid plan.

    Stripe: updates the subscription price with proration.
    Razorpay: cancels the current subscription immediately and creates a new one.
    """
    require_business_access(ctx, business_id)
    sub = await billing_service.get_or_create_subscription(session, business_id)

    if sub.plan == body.plan:
        return SubscriptionResponse.model_validate(sub)

    if sub.status not in ("active", "trialing"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription to change. Please subscribe first via /checkout.",
        )

    old_plan = sub.plan

    if sub.payment_provider == "stripe" and sub.stripe_subscription_id:
        await stripe_service.update_subscription_plan(sub.stripe_subscription_id, body.plan)
        sub.plan = body.plan

    elif sub.payment_provider == "razorpay" and sub.razorpay_subscription_id:
        await razorpay_service.cancel_subscription(sub.razorpay_subscription_id, at_cycle_end=False)
        new_rp_sub = await razorpay_service.create_subscription(
            plan=body.plan,
            business_id=str(business_id),
            customer_id=sub.razorpay_customer_id,
        )
        sub.razorpay_subscription_id = new_rp_sub["id"]
        sub.plan = body.plan
        sub.status = "active"

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found. Use /checkout to subscribe.",
        )

    await billing_service.record_billing_event(
        session,
        business_id=business_id,
        event_type="plan_changed",
        payload={"old_plan": old_plan, "new_plan": body.plan, "provider": sub.payment_provider},
    )
    await session.commit()
    return SubscriptionResponse.model_validate(sub)


@router.post("/{business_id}/cancel", response_model=CancelResponse)
async def cancel_subscription(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> CancelResponse:
    """Schedule the subscription to cancel at the end of the current period."""
    require_business_access(ctx, business_id)
    sub = await billing_service.get_or_create_subscription(session, business_id)

    if sub.status not in ("active", "trialing") or sub.plan == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active paid subscription to cancel",
        )

    if sub.payment_provider == "stripe" and sub.stripe_subscription_id:
        await stripe_service.cancel_at_period_end(sub.stripe_subscription_id)
    elif sub.payment_provider == "razorpay" and sub.razorpay_subscription_id:
        await razorpay_service.cancel_subscription(sub.razorpay_subscription_id, at_cycle_end=True)

    sub.cancel_at_period_end = True
    await billing_service.record_billing_event(
        session,
        business_id=business_id,
        event_type="subscription_cancel_scheduled",
        payload={"provider": sub.payment_provider},
    )
    await session.commit()

    return CancelResponse(
        cancel_at_period_end=True,
        current_period_end=sub.current_period_end,
        message="Your subscription will remain active until the end of the current billing period.",
    )


@router.post("/{business_id}/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Remove the pending cancellation (only possible before the period ends)."""
    require_business_access(ctx, business_id)
    sub = await billing_service.get_or_create_subscription(session, business_id)

    if not sub.cancel_at_period_end:
        return SubscriptionResponse.model_validate(sub)

    if sub.payment_provider == "stripe" and sub.stripe_subscription_id:
        await stripe_service.reactivate(sub.stripe_subscription_id)

    sub.cancel_at_period_end = False
    await billing_service.record_billing_event(
        session,
        business_id=business_id,
        event_type="subscription_reactivated",
        payload={"provider": sub.payment_provider},
    )
    await session.commit()
    return SubscriptionResponse.model_validate(sub)
