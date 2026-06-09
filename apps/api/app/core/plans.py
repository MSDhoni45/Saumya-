from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlanConfig:
    id: str
    name: str
    description: str
    message_limit: int | None  # None = unlimited (Agency plan)
    price_usd_cents: int
    price_inr_paise: int


PLANS: dict[str, PlanConfig] = {
    "free": PlanConfig(
        id="free",
        name="Free",
        description="Up to 50 AI replies per month",
        message_limit=50,
        price_usd_cents=0,
        price_inr_paise=0,
    ),
    "starter": PlanConfig(
        id="starter",
        name="Starter",
        description="1,000 AI replies per month",
        message_limit=1_000,
        price_usd_cents=999,
        price_inr_paise=99_900,
    ),
    "growth": PlanConfig(
        id="growth",
        name="Growth",
        description="5,000 AI replies per month",
        message_limit=5_000,
        price_usd_cents=2_999,
        price_inr_paise=299_900,
    ),
    "agency": PlanConfig(
        id="agency",
        name="Agency",
        description="Unlimited AI replies",
        message_limit=None,
        price_usd_cents=7_999,
        price_inr_paise=799_900,
    ),
}

# Display order: cheapest first.
ORDERED_PLANS: list[PlanConfig] = [PLANS["free"], PLANS["starter"], PLANS["growth"], PLANS["agency"]]

PAID_PLAN_IDS: frozenset[str] = frozenset({"starter", "growth", "agency"})


def get_plan(plan_id: str) -> PlanConfig:
    plan = PLANS.get(plan_id)
    if plan is None:
        raise ValueError(f"Unknown plan: {plan_id!r}")
    return plan
