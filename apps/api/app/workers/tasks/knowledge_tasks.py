import logging
import uuid

from app.db.session import async_session_factory
from app.models.agent import Document
from app.services.embeddings import embed_texts
from app.workers.celery_app import celery_app
from app.workers.tasks.agent_tasks import _get_worker_loop

logger = logging.getLogger(__name__)

# Max characters sent to the embedding model. text-embedding-3-small supports
# ~8 191 tokens; at ~4 chars/token that's ~32 k chars. We leave headroom.
_MAX_EMBED_CHARS = 30_000


@celery_app.task(name="knowledge.embed_document", bind=True, max_retries=3, default_retry_delay=30)
def embed_document(self, *, document_id: str) -> None:
    """Chunk and embed a newly-added knowledge base document.

    Status flow: pending → (processing is skipped for simplicity) → ready | error.
    On transient failures (API timeouts, rate limits) Celery retries up to 3×
    with exponential back-off; the document stays in `error` state after
    exhausting retries.
    """
    try:
        _get_worker_loop().run_until_complete(_embed_document(uuid.UUID(document_id)))
    except Exception as exc:
        logger.exception("Embedding failed for document_id=%s", document_id)
        raise self.retry(exc=exc) from exc


async def _embed_document(document_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        doc = await session.get(Document, document_id)
        if doc is None or doc.status not in ("pending", "error"):
            return

        try:
            (embedding,) = await embed_texts([doc.content[:_MAX_EMBED_CHARS]])
        except Exception as exc:
            doc.status = "error"
            doc.error_message = str(exc)[:500]
            await session.commit()
            raise

        doc.embedding = embedding
        doc.status = "ready"
        doc.error_message = None
        await session.commit()
