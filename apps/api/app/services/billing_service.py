from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import get_plan
from app.models.billing import BillingEvent, Subscription, UsageRecord

logger = logging.getLogger(__name__)


class UsageLimitExceeded(Exception):
    def __init__(self, plan: str, limit: int) -> None:
        self.plan = plan
        self.limit = limit
        super().__init__(
            f"Monthly limit of {limit:,} AI replies reached on the {plan.title()} plan. "
            "Upgrade your plan to continue sending AI replies."
        )


class SubscriptionInactive(Exception):
    """Raised when the business's subscription is in a state that should suppress AI replies.

    `paused` and `cancelled` block AI traffic outright. `past_due` is treated as
    still active (Stripe convention — dunning happens while service continues
    until the subscription is actually cancelled).
    """

    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(
            f"AI replies are paused — subscription is {status}. "
            "Reactivate billing to resume automated replies."
        )


# Subscription statuses that suppress AI replies. `past_due` intentionally
# absent: Stripe leaves the subscription functional during dunning, and our
# billing webhook flips it back to `active` on successful payment.
_BLOCKING_STATUSES = frozenset({"paused", "cancelled"})


def _period_start() -> datetime:
    now = datetime.now(tz=timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month(dt: datetime) -> datetime:
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1)
    return dt.replace(month=dt.month + 1)


async def get_or_create_subscription(session: AsyncSession, business_id: uuid.UUID) -> Subscription:
    sub = await session.scalar(select(Subscription).where(Subscription.business_id == business_id))
    if sub is None:
        sub = Subscription(business_id=business_id, plan="free", status="active")
        session.add(sub)
        await session.flush()
    return sub


async def get_current_usage(session: AsyncSession, business_id: uuid.UUID) -> UsageRecord:
    ps = _period_start()
    usage = await session.scalar(
        select(UsageRecord).where(
            UsageRecord.business_id == business_id,
            UsageRecord.period_start == ps,
        )
    )
    if usage is None:
        # Return an unsaved zero-count record for display purposes.
        # Callers that only read (e.g. the usage endpoint) won't persist it,
        # so the DB only grows one row per business per month that actually
        # sends at least one message.
        usage = UsageRecord(
            business_id=business_id,
            period_start=ps,
            period_end=_next_month(ps),
            message_count=0,
        )
    return usage


async def increment_usage(session: AsyncSession, business_id: uuid.UUID) -> int:
    """Atomically upsert the monthly message counter. Returns the new count."""
    ps = _period_start()
    result = await session.execute(
        text("""
            INSERT INTO usage_records (id, business_id, period_start, period_end, message_count)
            VALUES (gen_random_uuid(), :bid, :ps, :pe, 1)
            ON CONFLICT (business_id, period_start)
            DO UPDATE SET message_count = usage_records.message_count + 1,
                          updated_at    = NOW()
            RETURNING message_count
        """),
        {"bid": business_id, "ps": ps, "pe": _next_month(ps)},
    )
    row = result.fetchone()
    return row[0] if row else 1


async def check_usage_limit(session: AsyncSession, business_id: uuid.UUID) -> None:
    """Gate AI replies on subscription state and monthly usage.

    Raises:
        SubscriptionInactive: subscription is `paused` or `cancelled` — block
            outright regardless of plan or usage. Caller surfaces this to the
            operator inbox so they know why the bot went quiet.
        UsageLimitExceeded: subscription is otherwise live but the monthly
            message cap has been reached.
    """
    sub = await get_or_create_subscription(session, business_id)
    if sub.status in _BLOCKING_STATUSES:
        raise SubscriptionInactive(status=sub.status)
    plan = get_plan(sub.plan)
    if plan.message_limit is None:
        return  # Agency — unlimited
    usage = await get_current_usage(session, business_id)
    if usage.message_count >= plan.message_limit:
        raise UsageLimitExceeded(plan=sub.plan, limit=plan.message_limit)


async def activate_subscription(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    plan: str,
    provider: str,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    razorpay_customer_id: str | None = None,
    razorpay_subscription_id: str | None = None,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
) -> Subscription:
    sub = await get_or_create_subscription(session, business_id)
    sub.plan = plan
    sub.status = "active"
    sub.payment_provider = provider
    sub.cancel_at_period_end = False
    if stripe_customer_id:
        sub.stripe_customer_id = stripe_customer_id
    if stripe_subscription_id:
        sub.stripe_subscription_id = stripe_subscription_id
    if razorpay_customer_id:
        sub.razorpay_customer_id = razorpay_customer_id
    if razorpay_subscription_id:
        sub.razorpay_subscription_id = razorpay_subscription_id
    if current_period_start:
        sub.current_period_start = current_period_start
    if current_period_end:
        sub.current_period_end = current_period_end
    return sub


async def record_billing_event(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    event_type: str,
    payload: dict,
    provider: str | None = None,
    provider_event_id: str | None = None,
) -> None:
    """Append a billing event, skipping silently on duplicate provider_event_id."""
    if provider_event_id:
        existing = await session.scalar(
            select(BillingEvent).where(BillingEvent.provider_event_id == provider_event_id)
        )
        if existing is not None:
            logger.debug("Duplicate billing event %s — skipping", provider_event_id)
            return
    session.add(BillingEvent(
        business_id=business_id,
        event_type=event_type,
        provider=provider,
        provider_event_id=provider_event_id,
        payload=payload,
    ))
