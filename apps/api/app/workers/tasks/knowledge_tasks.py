import logging
import uuid

from sqlalchemy import delete

from app.db.session import async_session_factory
from app.models.agent import Document, DocumentChunk
from app.services.embeddings import chunk_text, embed_texts
from app.workers.celery_app import celery_app
from app.workers.tasks.agent_tasks import _get_worker_loop

logger = logging.getLogger(__name__)


@celery_app.task(name="knowledge.embed_document", bind=True, max_retries=3, default_retry_delay=30)
def embed_document(self, *, document_id: str) -> None:
    """Chunk and embed a newly-added knowledge base document.

    Status flow: pending → ready | failed.
    On transient failures (API timeouts, rate limits) Celery retries up to 3×
    with exponential back-off; the document stays in `failed` state after
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
        if doc is None or doc.status not in ("pending", "failed"):
            return

        try:
            chunks = chunk_text(doc.content)
            if not chunks:
                # Empty content — clear any prior chunks so we don't keep
                # stale embeddings around, then mark ready with no retrieval
                # surface.
                await session.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
                )
                doc.embedding = None
                doc.status = "ready"
                doc.error_message = None
                await session.commit()
                return

            embeddings = await embed_texts(chunks)
        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)[:500]
            await session.commit()
            raise

        # Idempotent re-embed: drop any prior chunks for this document so we
        # never end up with a mix of old + new vectors for the same content.
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        )

        session.add_all(
            [
                DocumentChunk(
                    document_id=doc.id,
                    business_id=doc.business_id,
                    chunk_index=i,
                    content=chunk,
                    embedding=embedding,
                )
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
            ]
        )

        # Keep `Document.embedding` populated with the first chunk's vector
        # for back-compat with any reader that has not yet migrated. New
        # retrieval reads from `document_chunks`.
        doc.embedding = embeddings[0]
        doc.status = "ready"
        doc.error_message = None
        await session.commit()
