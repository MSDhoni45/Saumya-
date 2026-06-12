"""Operator alerting service (P0.2).

Centralises creation of `operator_alerts` rows + the SSE fan-out so the worker
and webhook code can fire a single helper rather than each duplicating the
insert + publish dance.

The caller is responsible for committing the session — alerts are written
inline with the failure that produced them so a rollback erases both, never
leaving a half-recorded incident.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import OperatorAlert
from app.services.realtime import publish_operator_alert

logger = logging.getLogger(__name__)


# Alert kinds — stable string identifiers the frontend can switch on for
# rendering. New kinds never need a schema migration.
ALERT_KIND_SEND_FAILED = "whatsapp_send_failed"
ALERT_KIND_STATUS_FAILED = "message_status_failed"

# Severity is for UI ordering; "error" is the only level the current pipeline
# emits, but the column accepts anything so warnings/info can be added later.
SEVERITY_ERROR = "error"


async def create_alert(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    kind: str,
    title: str,
    body: str,
    conversation_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
    severity: str = SEVERITY_ERROR,
) -> OperatorAlert:
    """Insert an alert and broadcast it to the business's SSE channel.

    The publish step swallows its own errors (see `realtime.publish_*`) so
    a Redis outage never breaks the failure-recording path.
    """
    alert = OperatorAlert(
        business_id=business_id,
        conversation_id=conversation_id,
        message_id=message_id,
        kind=kind,
        severity=severity,
        title=title,
        body=body,
    )
    session.add(alert)
    await session.flush()

    await publish_operator_alert(
        business_id=str(business_id),
        alert_id=str(alert.id),
        kind=kind,
        severity=severity,
        title=title,
    )
    return alert


async def list_alerts(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    unack_only: bool = False,
    limit: int = 100,
) -> list[OperatorAlert]:
    stmt = select(OperatorAlert).where(OperatorAlert.business_id == business_id)
    if unack_only:
        stmt = stmt.where(OperatorAlert.acknowledged_at.is_(None))
    stmt = stmt.order_by(OperatorAlert.created_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def acknowledge_alert(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    alert_id: uuid.UUID,
    user_id: uuid.UUID,
) -> OperatorAlert | None:
    """Mark an alert acknowledged. Idempotent — re-acking is a no-op.

    Returns `None` if the alert doesn't exist or belongs to a different
    business (callers should 404).
    """
    from datetime import datetime, timezone

    alert = await session.get(OperatorAlert, alert_id)
    if alert is None or alert.business_id != business_id:
        return None
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(tz=timezone.utc)
        alert.acknowledged_by = user_id
        await session.flush()
    return alert
