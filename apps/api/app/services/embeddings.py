import re
from functools import lru_cache

from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

# Roughly four characters per token for English prose — good enough to keep
# chunks well under the embedding model's context window without an extra
# tokenizer dependency.
_CHARS_PER_CHUNK = 1800
_CHARS_OVERLAP = 200
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


@lru_cache
def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


def chunk_text(text: str, *, chunk_size: int = _CHARS_PER_CHUNK, overlap: int = _CHARS_OVERLAP) -> list[str]:
    """Split source text into overlapping chunks along paragraph boundaries.

    Overlap keeps a sentence that straddles a chunk boundary retrievable from
    either side, which matters for RAG recall on long-form documents.
    """
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = current[-overlap:] + "\n\n" + paragraph if overlap else paragraph
        else:
            # A single paragraph longer than chunk_size — hard-split it.
            for start in range(0, len(paragraph), chunk_size - overlap):
                chunks.append(paragraph[start : start + chunk_size])
            current = ""

    if current:
        chunks.append(current)

    return chunks


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of strings using the configured model."""
    if not texts:
        return []

    response = await _client().embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )
    return [item.embedding for item in response.data]


async def embed_text(text: str) -> list[float]:
    (embedding,) = await embed_texts([text])
    return embedding
