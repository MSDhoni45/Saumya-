from celery import Celery

from app.core.config import settings

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
)
