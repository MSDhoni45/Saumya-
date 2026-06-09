from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, Field


class DayStat(BaseModel):
    date: str  # YYYY-MM-DD
    count: int


class LeadSourceStat(BaseModel):
    source: str
    count: int


class MetricTrend(BaseModel):
    value: float
    change_pct: float | None = None  # positive = up vs previous period; None = no prior data


class AnalyticsOverview(BaseModel):
    period_days: Annotated[int, Field(ge=1)]
    # Counts
    conversations: MetricTrend
    leads: MetricTrend
    conversion_rate: MetricTrend  # percent 0–100
    # AI performance
    ai_response_time_ms: float | None  # median latency
    ai_response_time_p95_ms: float | None
    # Human involvement
    human_takeovers: int
    human_takeover_rate: float  # percent of conversations in period
    # Lead pipeline
    qualification_rate: MetricTrend  # leads qualified/won ÷ total leads, percent
    lead_sources: list[LeadSourceStat]
    # Time-series for charts
    conversation_series: list[DayStat]
    lead_series: list[DayStat]
