from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.session import async_session_factory
from app.workers.celery_app import celery_app
from app.workers.tasks.agent_tasks import _get_worker_loop

logger = logging.getLogger(__name__)


@celery_app.task(name="billing.expire_subscriptions", bind=True, max_retries=2, default_retry_delay=60)
def expire_subscriptions(self) -> None:
    """Downgrade businesses whose paid subscription has lapsed (run nightly via Celery beat).

    Any subscription with cancel_at_period_end=TRUE whose current_period_end is in the
    past gets reset to the free plan. This is a safety net — normally the provider
    webhook (subscription.deleted / subscription.cancelled) fires first.
    """
    try:
        _get_worker_loop().run_until_complete(_expire_subscriptions())
    except Exception as exc:
        logger.exception("billing.expire_subscriptions failed")
        raise self.retry(exc=exc) from exc


async def _expire_subscriptions() -> None:
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                text("""
                    UPDATE subscriptions
                    SET plan             = 'free',
                        status          = 'cancelled',
                        payment_provider = NULL,
                        updated_at       = NOW()
                    WHERE cancel_at_period_end = TRUE
                      AND current_period_end   < NOW()
                      AND plan                != 'free'
                    RETURNING business_id
                """)
            )
            rows = result.fetchall()
            if rows:
                logger.info("expire_subscriptions: downgraded %d lapsed subscriptions to free", len(rows))
            await session.commit()
        except Exception:
            await session.rollback()
            raise
