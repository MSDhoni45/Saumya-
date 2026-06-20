"""Platform-operator endpoints for pilot-phase manual billing.

Used while `BILLING_ENABLED=false` to flip a business onto a paid plan after
out-of-band payment (UPI, bank transfer, invoice). Restricted to `super_admin`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.plans import get_plan
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.billing import SubscriptionResponse
from app.services import billing_service
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


class ManualActivationRequest(BaseModel):
    plan: str = Field(..., description="starter | growth | agency | free")
    period_days: int = Field(30, ge=1, le=400)
    note: str | None = None


@router.post(
    "/businesses/{business_id}/activate",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
)
async def activate_business(
    business_id: uuid.UUID,
    body: ManualActivationRequest,
    current_user: User = Depends(require_roles("super_admin")),
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Manually activate a paid subscription. Use during pilot before Stripe/Razorpay are connected."""
    try:
        get_plan(body.plan)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown plan: {body.plan}",
        ) from exc

    sub = await billing_service.get_or_create_subscription(session, business_id)
    now = datetime.now(tz=timezone.utc)

    sub.plan = body.plan
    sub.status = "active"
    sub.payment_provider = "manual"
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=body.period_days)
    sub.cancel_at_period_end = False

    await billing_service.record_billing_event(
        session,
        business_id=business_id,
        event_type="manual_activation",
        payload={
            "plan": body.plan,
            "period_days": body.period_days,
            "operator_user_id": str(current_user.id),
            "note": body.note,
        },
    )
    await session.commit()
    await session.refresh(sub)
    logger.info(
        "manual subscription activation business_id=%s plan=%s operator=%s",
        business_id, body.plan, current_user.id,
    )
    return SubscriptionResponse.model_validate(sub)


@router.post(
    "/businesses/{business_id}/deactivate",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
)
async def deactivate_business(
    business_id: uuid.UUID,
    current_user: User = Depends(require_roles("super_admin")),
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Move business back to the free plan."""
    sub = await billing_service.get_or_create_subscription(session, business_id)
    sub.plan = "free"
    sub.status = "active"
    sub.cancel_at_period_end = False

    await billing_service.record_billing_event(
        session,
        business_id=business_id,
        event_type="manual_deactivation",
        payload={"operator_user_id": str(current_user.id)},
    )
    await session.commit()
    await session.refresh(sub)
    logger.info(
        "manual subscription deactivation business_id=%s operator=%s",
        business_id, current_user.id,
    )
    return SubscriptionResponse.model_validate(sub)
