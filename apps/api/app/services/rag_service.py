import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Document, DocumentChunk
from app.services.embeddings import embed_text

# Below this similarity, a chunk is more likely to confuse the model than help
# it — better to answer "I'm not sure" than to hallucinate from a weak match.
_MIN_SIMILARITY = 0.7


class RetrievedChunk:
    __slots__ = ("chunk_id", "chunk_index", "document_id", "title", "content", "similarity")

    def __init__(
        self,
        *,
        chunk_id: uuid.UUID,
        chunk_index: int,
        document_id: uuid.UUID,
        title: str,
        content: str,
        similarity: float,
    ) -> None:
        self.chunk_id = chunk_id
        self.chunk_index = chunk_index
        self.document_id = document_id
        self.title = title
        self.content = content
        self.similarity = similarity


async def retrieve_relevant_chunks(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    query: str,
    top_k: int = 4,
    min_similarity: float = _MIN_SIMILARITY,
) -> list[RetrievedChunk]:
    """Find the `top_k` most relevant document chunks for `query`.

    Cosine *distance* (`<=>`) ranges 0 (identical) to 2 (opposite); for
    normalized embeddings `1 - distance` is the standard cosine-similarity form,
    so callers and the `min_similarity` threshold can reason in intuitive terms.

    Reads from `document_chunks` (one row per token-bounded slice) joined to
    `documents` for the parent title and the status filter — `Document.embedding`
    is no longer used for retrieval but is kept populated for back-compat.
    """
    query_embedding = await embed_text(query)
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    similarity = (1 - distance).label("similarity")

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.chunk_index,
            DocumentChunk.document_id,
            Document.title,
            DocumentChunk.content,
            similarity,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.business_id == business_id,
            Document.status == "ready",
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(top_k)
    )

    rows = (await session.execute(stmt)).all()
    return [
        RetrievedChunk(
            chunk_id=row.id,
            chunk_index=row.chunk_index,
            document_id=row.document_id,
            title=row.title,
            content=row.content,
            similarity=float(row.similarity),
        )
        for row in rows
        if row.similarity >= min_similarity
    ]


def format_chunks_for_prompt(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks as a numbered context block for the system prompt."""
    if not chunks:
        return "No relevant business documents were found for this query."

    return "\n\n".join(f"[{i}] {chunk.title}\n{chunk.content}" for i, chunk in enumerate(chunks, start=1))
