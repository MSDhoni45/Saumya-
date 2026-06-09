from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics import AnalyticsOverview, DayStat, LeadSourceStat, MetricTrend


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _fill_series(rows: list[tuple[date, int]], start: datetime, days: int) -> list[DayStat]:
    by_date: dict[date, int] = {r[0]: r[1] for r in rows}
    series: list[DayStat] = []
    for i in range(days):
        d = (start + timedelta(days=i)).date()
        series.append(DayStat(date=d.isoformat(), count=by_date.get(d, 0)))
    return series


async def get_overview(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    days: int,
) -> AnalyticsOverview:
    now = datetime.now(tz=timezone.utc)
    end = now
    start = end - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    params = {
        "bid": str(business_id),
        "start": start,
        "end": end,
        "prev_start": prev_start,
    }

    # ------------------------------------------------------------------ #
    # Core aggregates — single round-trip with multiple CTEs
    # ------------------------------------------------------------------ #
    agg = (await session.execute(text("""
        WITH
          conv_curr AS (
            SELECT COUNT(*)::int AS n
            FROM conversations
            WHERE business_id = :bid::uuid AND created_at >= :start AND created_at < :end
          ),
          conv_prev AS (
            SELECT COUNT(*)::int AS n
            FROM conversations
            WHERE business_id = :bid::uuid AND created_at >= :prev_start AND created_at < :start
          ),
          lead_curr AS (
            SELECT COUNT(*)::int AS n
            FROM leads
            WHERE business_id = :bid::uuid AND created_at >= :start AND created_at < :end
          ),
          lead_prev AS (
            SELECT COUNT(*)::int AS n
            FROM leads
            WHERE business_id = :bid::uuid AND created_at >= :prev_start AND created_at < :start
          ),
          qualified_curr AS (
            SELECT COUNT(*)::int AS n
            FROM leads
            WHERE business_id = :bid::uuid
              AND stage IN ('qualified', 'won')
              AND created_at >= :start AND created_at < :end
          ),
          qualified_prev AS (
            SELECT COUNT(*)::int AS n
            FROM leads
            WHERE business_id = :bid::uuid
              AND stage IN ('qualified', 'won')
              AND created_at >= :prev_start AND created_at < :start
          ),
          takeover_curr AS (
            SELECT COUNT(*)::int AS n
            FROM conversations
            WHERE business_id = :bid::uuid
              AND status = 'handoff'
              AND created_at >= :start AND created_at < :end
          ),
          latency AS (
            SELECT
              PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50,
              PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95
            FROM ai_interactions
            WHERE business_id = :bid::uuid
              AND latency_ms IS NOT NULL
              AND created_at >= :start AND created_at < :end
          )
        SELECT
          (SELECT n FROM conv_curr)        AS conv_curr,
          (SELECT n FROM conv_prev)        AS conv_prev,
          (SELECT n FROM lead_curr)        AS lead_curr,
          (SELECT n FROM lead_prev)        AS lead_prev,
          (SELECT n FROM qualified_curr)   AS qual_curr,
          (SELECT n FROM qualified_prev)   AS qual_prev,
          (SELECT n FROM takeover_curr)    AS takeovers,
          (SELECT p50 FROM latency)        AS ai_p50,
          (SELECT p95 FROM latency)        AS ai_p95
    """), params)).mappings().one()

    conv_curr: int = agg["conv_curr"] or 0
    conv_prev: int = agg["conv_prev"] or 0
    lead_curr: int = agg["lead_curr"] or 0
    lead_prev: int = agg["lead_prev"] or 0
    qual_curr: int = agg["qual_curr"] or 0
    qual_prev: int = agg["qual_prev"] or 0
    takeovers: int = agg["takeovers"] or 0

    # ------------------------------------------------------------------ #
    # Derived metrics
    # ------------------------------------------------------------------ #
    conv_rate_curr = round(lead_curr / conv_curr * 100, 1) if conv_curr else 0.0
    conv_rate_prev_denom = conv_prev
    conv_rate_prev = round(lead_prev / conv_rate_prev_denom * 100, 1) if conv_rate_prev_denom else 0.0

    qual_rate_curr = round(qual_curr / lead_curr * 100, 1) if lead_curr else 0.0
    qual_rate_prev = round(qual_prev / lead_prev * 100, 1) if lead_prev else 0.0

    takeover_rate = round(takeovers / conv_curr * 100, 1) if conv_curr else 0.0

    # ------------------------------------------------------------------ #
    # Lead sources
    # ------------------------------------------------------------------ #
    sources_rows = (await session.execute(text("""
        SELECT COALESCE(source, 'unknown') AS source, COUNT(*)::int AS cnt
        FROM leads
        WHERE business_id = :bid::uuid AND created_at >= :start AND created_at < :end
        GROUP BY source
        ORDER BY cnt DESC
    """), params)).all()

    lead_sources = [LeadSourceStat(source=r[0], count=r[1]) for r in sources_rows]

    # ------------------------------------------------------------------ #
    # Daily time-series
    # ------------------------------------------------------------------ #
    conv_series_rows = (await session.execute(text("""
        SELECT created_at::date AS d, COUNT(*)::int AS cnt
        FROM conversations
        WHERE business_id = :bid::uuid AND created_at >= :start AND created_at < :end
        GROUP BY 1
        ORDER BY 1
    """), params)).all()

    lead_series_rows = (await session.execute(text("""
        SELECT created_at::date AS d, COUNT(*)::int AS cnt
        FROM leads
        WHERE business_id = :bid::uuid AND created_at >= :start AND created_at < :end
        GROUP BY 1
        ORDER BY 1
    """), params)).all()

    return AnalyticsOverview(
        period_days=days,
        conversations=MetricTrend(
            value=conv_curr,
            change_pct=_pct_change(conv_curr, conv_prev),
        ),
        leads=MetricTrend(
            value=lead_curr,
            change_pct=_pct_change(lead_curr, lead_prev),
        ),
        conversion_rate=MetricTrend(
            value=conv_rate_curr,
            change_pct=_pct_change(conv_rate_curr, conv_rate_prev),
        ),
        ai_response_time_ms=float(agg["ai_p50"]) if agg["ai_p50"] is not None else None,
        ai_response_time_p95_ms=float(agg["ai_p95"]) if agg["ai_p95"] is not None else None,
        human_takeovers=takeovers,
        human_takeover_rate=takeover_rate,
        qualification_rate=MetricTrend(
            value=qual_rate_curr,
            change_pct=_pct_change(qual_rate_curr, qual_rate_prev),
        ),
        lead_sources=lead_sources,
        conversation_series=_fill_series([(r[0], r[1]) for r in conv_series_rows], start, days),
        lead_series=_fill_series([(r[0], r[1]) for r in lead_series_rows], start, days),
    )
