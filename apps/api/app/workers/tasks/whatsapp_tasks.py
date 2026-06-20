from __future__ import annotations

import logging

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.whatsapp import WhatsAppAccount
from app.services.encryption import decrypt_secret
from app.services.whatsapp_client import WhatsAppApiError, WhatsAppClient
from app.workers.celery_app import celery_app
from app.workers.tasks.agent_tasks import _get_worker_loop

logger = logging.getLogger(__name__)


@celery_app.task(name="whatsapp.check_token_health", bind=True, max_retries=1, default_retry_delay=120)
def check_token_health(self) -> None:
    """Daily liveness probe for every connected WhatsApp access token.

    System-User tokens don't auto-rotate; if the operator regenerates or
    revokes one in Business Manager we only find out the next time a
    customer message fails. This probes /phone-number-id daily so the
    breakage surfaces (Sentry + DB status flip) before a customer feels it.
    """
    try:
        _get_worker_loop().run_until_complete(_check_token_health())
    except Exception as exc:
        logger.exception("whatsapp.check_token_health failed")
        raise self.retry(exc=exc) from exc


async def _check_token_health() -> None:
    async with async_session_factory() as session:
        rows = await session.execute(
            select(WhatsAppAccount).where(
                WhatsAppAccount.status == "connected",
                WhatsAppAccount.access_token.is_not(None),
            )
        )
        accounts = list(rows.scalars().all())

        revoked = 0
        for account in accounts:
            try:
                token = decrypt_secret(account.access_token)
                client = WhatsAppClient(
                    phone_number_id=account.phone_number_id,
                    access_token=token,
                )
                ok = await client.verify_token()
            except (WhatsAppApiError, Exception):
                logger.exception(
                    "whatsapp token probe crashed business_id=%s account_id=%s",
                    account.business_id, account.id,
                )
                continue

            if not ok:
                revoked += 1
                account.status = "token_invalid"
                logger.error(
                    "whatsapp token revoked or expired business_id=%s account_id=%s — operator action required",
                    account.business_id, account.id,
                )

        if revoked:
            await session.commit()
            logger.warning("whatsapp.check_token_health: %d account(s) marked token_invalid", revoked)
