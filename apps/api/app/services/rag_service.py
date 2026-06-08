import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Document
from app.services.embeddings import embed_text

# Below this similarity, a chunk is more likely to confuse the model than help
# it — better to answer "I'm not sure" than to hallucinate from a weak match.
_MIN_SIMILARITY = 0.7


class RetrievedChunk:
    __slots__ = ("document_id", "title", "content", "similarity")

    def __init__(self, *, document_id: uuid.UUID, title: str, content: str, similarity: float) -> None:
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
    """Find the `top_k` most relevant ready document chunks for `query`.

    Cosine *distance* (`<=>`) ranges 0 (identical) to 2 (opposite); we convert
    to a similarity score in [0, 1] (`1 - distance / 2`... but for normalized
    embeddings `1 - distance` is the standard cosine-similarity form) so
    callers and the `min_similarity` threshold can reason in intuitive terms.
    """
    query_embedding = await embed_text(query)
    distance = Document.embedding.cosine_distance(query_embedding)
    similarity = (1 - distance).label("similarity")

    stmt = (
        select(Document.id, Document.title, Document.content, similarity)
        .where(
            Document.business_id == business_id,
            Document.status == "ready",
            Document.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(top_k)
    )

    rows = (await session.execute(stmt)).all()
    return [
        RetrievedChunk(document_id=row.id, title=row.title, content=row.content, similarity=float(row.similarity))
        for row in rows
        if row.similarity >= min_similarity
    ]


def format_chunks_for_prompt(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks as a numbered context block for the system prompt."""
    if not chunks:
        return "No relevant business documents were found for this query."

    return "\n\n".join(f"[{i}] {chunk.title}\n{chunk.content}" for i, chunk in enumerate(chunks, start=1))
