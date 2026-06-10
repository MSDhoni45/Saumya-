import logging
from typing import Any

from celery import Celery
from celery.schedules import crontab
from celery.signals import celeryd_init, task_failure

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "whatsagent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks.agent_tasks",
        "app.workers.tasks.knowledge_tasks",
        "app.workers.tasks.billing_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Replies call out to the LLM and the WhatsApp Graph API — both can be
    # slow; ack-late + a soft limit means a crashed worker doesn't silently
    # drop a contact's message.
    task_acks_late=True,
    task_soft_time_limit=55,
    task_time_limit=75,
    beat_schedule={
        "expire-overdue-subscriptions": {
            "task": "billing.expire_subscriptions",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)


@celeryd_init.connect
def _init_sentry(**_kwargs: Any) -> None:
    """Initialize Sentry in the worker process.

    The API process initializes Sentry in `create_app()`, but workers never
    import `app.main` — without this, task exceptions were invisible to
    Sentry. CeleryIntegration captures unhandled task exceptions (including
    final failures after retries) with task name/args context.
    """
    if not settings.sentry_dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        environment=settings.environment,
        integrations=[CeleryIntegration()],
        send_default_pii=False,
    )


@task_failure.connect
def _log_task_failure(
    task_id: str | None = None,
    exception: BaseException | None = None,
    sender: Any = None,
    **_kwargs: Any,
) -> None:
    # Structured log on every failure — keeps failures observable in container
    # logs even when Sentry is not configured (Sentry capture itself is
    # handled by CeleryIntegration above).
    logger.error(
        "Celery task failed: task=%s id=%s error=%s: %s",
        getattr(sender, "name", "unknown"),
        task_id,
        type(exception).__name__ if exception else "unknown",
        exception,
        exc_info=exception,
    )
