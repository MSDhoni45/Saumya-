"""Tests for the RAG chunking pipeline (P0 — replaces single-vector-per-doc).

The earlier implementation truncated every document at 30 000 chars and stored
exactly one embedding on the parent row. That collapsed long-form content into
a single fuzzy vector and silently dropped anything past the cap. These tests
lock in the new behaviour: token-bounded chunks, multiple embeddings, retrieval
from `document_chunks`, idempotent re-embed, and stable identifiers stored on
`AiInteraction.retrieved_chunk_ids`.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embeddings import chunk_text


# ---------------------------------------------------------------------------
# chunk_text — pure function, no I/O
# ---------------------------------------------------------------------------


def test_chunk_text_splits_long_document_into_multiple_chunks():
    # 30 paragraphs × ~200 chars each = ~6 000 chars, well above the 1 800
    # chunk_size so we must emit more than one chunk.
    paragraphs = ["lorem ipsum dolor sit amet " * 8 for _ in range(30)]
    text = "\n\n".join(paragraphs)

    chunks = chunk_text(text)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.strip(), "no empty chunks"


def test_chunk_text_does_not_truncate_50k_document():
    # Pre-fix behaviour was `text[:30_000]` — anything past 30 k was thrown
    # away. Assert that every paragraph (including the very last) survives
    # somewhere in the chunk set.
    paragraphs = [f"paragraph-{i} " + ("x" * 500) for i in range(100)]
    text = "\n\n".join(paragraphs)
    assert len(text) > 50_000

    chunks = chunk_text(text)
    joined = "\n".join(chunks)

    # First and last paragraph markers must both appear — proves no truncation
    # at either end and that the splitter walked the full input.
    assert "paragraph-0 " in joined
    assert "paragraph-99 " in joined


def test_chunk_text_handles_empty_document():
    assert chunk_text("") == []
    assert chunk_text("   \n\n   ") == []


# ---------------------------------------------------------------------------
# Worker — _embed_document
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_document():
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.business_id = uuid.uuid4()
    doc.content = "first paragraph.\n\n" + "long body " * 400
    doc.status = "pending"
    doc.embedding = None
    doc.error_message = None
    return doc


async def test_embed_document_chunks_and_inserts_rows(fake_document):
    """Worker must chunk, embed per chunk, delete prior chunks, bulk insert."""
    from app.workers.tasks import knowledge_tasks

    session = AsyncMock()
    session.add_all = MagicMock()
    session.execute = AsyncMock()
    session.get = AsyncMock(return_value=fake_document)

    fake_chunks = ["chunk one body", "chunk two body", "chunk three body"]
    fake_vectors = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(knowledge_tasks, "async_session_factory", return_value=cm),
        patch.object(knowledge_tasks, "chunk_text", return_value=fake_chunks) as mock_chunk,
        patch.object(knowledge_tasks, "embed_texts", AsyncMock(return_value=fake_vectors)) as mock_embed,
    ):
        await knowledge_tasks._embed_document(fake_document.id)

    # Chunked the full content (no truncation passed in).
    mock_chunk.assert_called_once_with(fake_document.content)
    # Embedded every chunk in one batch.
    mock_embed.assert_awaited_once_with(fake_chunks)

    # Bulk-inserted exactly len(chunks) rows.
    assert session.add_all.call_count == 1
    inserted = session.add_all.call_args.args[0]
    assert len(inserted) == len(fake_chunks)
    # chunk_index is monotonic + matches content.
    for i, row in enumerate(inserted):
        assert row.chunk_index == i
        assert row.content == fake_chunks[i]
        assert row.document_id == fake_document.id
        assert row.business_id == fake_document.business_id

    # Idempotent re-embed: must have deleted prior chunks before inserting.
    assert session.execute.await_count >= 1

    # Back-compat: parent row keeps the first chunk's embedding.
    assert fake_document.embedding == fake_vectors[0]
    assert fake_document.status == "ready"


async def test_embed_document_empty_content_clears_chunks(fake_document):
    """An empty doc must still mark `ready` and not call the embedding API."""
    from app.workers.tasks import knowledge_tasks

    fake_document.content = ""
    session = AsyncMock()
    session.add_all = MagicMock()
    session.execute = AsyncMock()
    session.get = AsyncMock(return_value=fake_document)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(knowledge_tasks, "async_session_factory", return_value=cm),
        patch.object(knowledge_tasks, "embed_texts", AsyncMock()) as mock_embed,
    ):
        await knowledge_tasks._embed_document(fake_document.id)

    mock_embed.assert_not_awaited()
    session.add_all.assert_not_called()
    assert fake_document.status == "ready"
    assert fake_document.embedding is None


async def test_embed_document_idempotent_on_rerun(fake_document):
    """Re-embedding the same doc must always delete-then-insert, never append."""
    from app.workers.tasks import knowledge_tasks

    session = AsyncMock()
    session.add_all = MagicMock()
    session.execute = AsyncMock()
    session.get = AsyncMock(return_value=fake_document)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)

    fake_chunks = ["only one"]
    fake_vectors = [[0.5] * 1536]

    # Worker only re-runs on pending/failed — simulate a retry after a failure.
    fake_document.status = "failed"

    with (
        patch.object(knowledge_tasks, "async_session_factory", return_value=cm),
        patch.object(knowledge_tasks, "chunk_text", return_value=fake_chunks),
        patch.object(knowledge_tasks, "embed_texts", AsyncMock(return_value=fake_vectors)),
    ):
        await knowledge_tasks._embed_document(fake_document.id)

    # Must have issued the delete-chunks statement before inserting new rows.
    assert session.execute.await_count >= 1
    assert session.add_all.call_count == 1


# ---------------------------------------------------------------------------
# rag_service — retrieve_relevant_chunks
# ---------------------------------------------------------------------------


async def test_retrieve_relevant_chunks_returns_chunk_identity():
    """Retrieval must surface chunk_id + chunk_index + document_id, not raw docs."""
    from app.services import rag_service

    business_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    document_id = uuid.uuid4()

    row = MagicMock()
    row.id = chunk_id
    row.chunk_index = 3
    row.document_id = document_id
    row.title = "Pricing FAQ"
    row.content = "Plan A is $99/mo."
    row.similarity = 0.91

    result = MagicMock()
    result.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    with patch.object(rag_service, "embed_text", AsyncMock(return_value=[0.0] * 1536)):
        chunks = await rag_service.retrieve_relevant_chunks(
            session, business_id=business_id, query="how much does Plan A cost?"
        )

    assert len(chunks) == 1
    got = chunks[0]
    assert got.chunk_id == chunk_id
    assert got.chunk_index == 3
    assert got.document_id == document_id
    assert got.title == "Pricing FAQ"
    assert got.content == "Plan A is $99/mo."
    assert got.similarity == pytest.approx(0.91)


async def test_retrieve_relevant_chunks_drops_below_min_similarity():
    """Sub-threshold matches must be filtered — better silence than hallucination."""
    from app.services import rag_service

    row_high = MagicMock()
    row_high.id = uuid.uuid4()
    row_high.chunk_index = 0
    row_high.document_id = uuid.uuid4()
    row_high.title = "ok"
    row_high.content = "good match"
    row_high.similarity = 0.85

    row_low = MagicMock()
    row_low.id = uuid.uuid4()
    row_low.chunk_index = 0
    row_low.document_id = uuid.uuid4()
    row_low.title = "weak"
    row_low.content = "weak match"
    row_low.similarity = 0.42  # below 0.7 floor

    result = MagicMock()
    result.all.return_value = [row_high, row_low]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    with patch.object(rag_service, "embed_text", AsyncMock(return_value=[0.0] * 1536)):
        chunks = await rag_service.retrieve_relevant_chunks(
            session, business_id=uuid.uuid4(), query="anything"
        )

    assert len(chunks) == 1
    assert chunks[0].content == "good match"


def test_format_chunks_uses_titles_and_content():
    from app.services.rag_service import RetrievedChunk, format_chunks_for_prompt

    a = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        document_id=uuid.uuid4(),
        title="FAQ",
        content="answer one",
        similarity=0.9,
    )
    b = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        chunk_index=1,
        document_id=uuid.uuid4(),
        title="Pricing",
        content="answer two",
        similarity=0.8,
    )

    rendered = format_chunks_for_prompt([a, b])

    assert "[1] FAQ" in rendered
    assert "answer one" in rendered
    assert "[2] Pricing" in rendered
    assert "answer two" in rendered


def test_format_chunks_empty_has_safe_fallback():
    from app.services.rag_service import format_chunks_for_prompt

    rendered = format_chunks_for_prompt([])
    assert "No relevant business documents" in rendered


# ---------------------------------------------------------------------------
# sales_agent_service — retrieved_chunk_ids identifies CHUNKS, not documents
# ---------------------------------------------------------------------------


async def test_record_interaction_stores_chunk_ids_not_document_ids():
    """`AiInteraction.retrieved_chunk_ids` must hold the chunk PKs.

    Storing document_ids was lossy — multiple chunks from the same doc
    collapsed to duplicate rows, and analytics couldn't tell which passage
    the model was actually grounded on.
    """
    from app.services import sales_agent_service
    from app.services.rag_service import RetrievedChunk

    document_id = uuid.uuid4()
    chunk_a_id = uuid.uuid4()
    chunk_b_id = uuid.uuid4()

    chunks = [
        RetrievedChunk(
            chunk_id=chunk_a_id,
            chunk_index=0,
            document_id=document_id,
            title="FAQ",
            content="one",
            similarity=0.9,
        ),
        RetrievedChunk(
            chunk_id=chunk_b_id,
            chunk_index=1,
            document_id=document_id,
            title="FAQ",
            content="two",
            similarity=0.85,
        ),
    ]

    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.business_id = uuid.uuid4()
    agent.provider = "openai"
    agent.model = "gpt-4o-mini"

    result = sales_agent_service.AgentReplyResult(
        reply="hi",
        extracted_lead_fields={},
        retrieved_chunks=chunks,
        prompt_tokens=10,
        completion_tokens=5,
        latency_ms=120,
    )

    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    interaction = await sales_agent_service.record_interaction(
        session,
        agent=agent,
        conversation_id=uuid.uuid4(),
        inbound_message_id=uuid.uuid4(),
        outbound_message_id=uuid.uuid4(),
        result=result,
    )

    assert interaction.retrieved_chunk_ids == [chunk_a_id, chunk_b_id]
    assert document_id not in interaction.retrieved_chunk_ids
