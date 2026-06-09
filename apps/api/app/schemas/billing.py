from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PlanResponse(BaseModel):
    id: str
    name: str
    description: str
    message_limit: int | None  # None = unlimited
    price_usd_cents: int
    price_inr_paise: int
    is_current: bool = False


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    plan: str
    status: str
    payment_provider: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    trial_ends_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UsageResponse(BaseModel):
    business_id: uuid.UUID
    plan: str
    message_limit: int | None
    message_count: int
    period_start: datetime | None
    period_end: datetime | None
    percent_used: float | None  # None when plan is unlimited


class CheckoutRequest(BaseModel):
    plan: Literal["starter", "growth", "agency"]
    provider: Literal["stripe", "razorpay"]
    success_url: str | None = None
    cancel_url: str | None = None


class StripeCheckoutResponse(BaseModel):
    provider: Literal["stripe"] = "stripe"
    checkout_url: str


class RazorpayCheckoutResponse(BaseModel):
    provider: Literal["razorpay"] = "razorpay"
    razorpay_subscription_id: str
    razorpay_key_id: str
    amount: int  # in paise
    currency: str = "INR"
    business_name: str


class ChangePlanRequest(BaseModel):
    plan: Literal["starter", "growth", "agency"]


class CancelResponse(BaseModel):
    cancel_at_period_end: bool
    current_period_end: datetime | None
    message: str
