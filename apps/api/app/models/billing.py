from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

_TZ = DateTime(timezone=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    # free | starter | growth | agency
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    # active | trialing | past_due | cancelled | paused
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    # stripe | razorpay | null (free plan, no provider)
    payment_provider: Mapped[str | None] = mapped_column(String(50))

    # Stripe
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)

    # Razorpay
    razorpay_customer_id: Mapped[str | None] = mapped_column(String(255))
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)

    current_period_start: Mapped[datetime | None] = mapped_column(_TZ)
    current_period_end: Mapped[datetime | None] = mapped_column(_TZ)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(_TZ)

    created_at: Mapped[datetime] = mapped_column(_TZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ, nullable=False, server_default=func.now(), onupdate=func.now())


class UsageRecord(Base):
    """Monthly message usage per business. One row per (business, billing period)."""

    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    period_start: Mapped[datetime] = mapped_column(_TZ, nullable=False)
    period_end: Mapped[datetime] = mapped_column(_TZ, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(_TZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ, nullable=False, server_default=func.now(), onupdate=func.now())


class BillingEvent(Base):
    """Immutable append-only audit log of billing activity.

    `provider_event_id` is the idempotency key: if a webhook is re-delivered
    the duplicate write is silently skipped, so every provider event is
    processed exactly once.
    """

    __tablename__ = "billing_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(50))
    provider_event_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(_TZ, nullable=False, server_default=func.now())
