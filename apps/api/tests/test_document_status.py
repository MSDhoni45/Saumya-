"""Tests for canonical document.status handling in the knowledge worker.

DB CHECK constraint allows ('pending','processing','ready','failed'). The
worker historically wrote 'error' — a value the constraint rejects. These
tests pin the canonical value end-to-end so the worker can never regress.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.tasks import knowledge_tasks


@pytest.fixture
def fake_session() -> MagicMock:
    session = MagicMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


async def _run_with_session(session: MagicMock, document_id: uuid.UUID) -> None:
    factory_cm = MagicMock()
    factory_cm.__aenter__ = AsyncMock(return_value=session)
    factory_cm.__aexit__ = AsyncMock(return_value=False)
    with patch.object(knowledge_tasks, "async_session_factory", return_value=factory_cm):
        await knowledge_tasks._embed_document(document_id)


def _make_doc(*, status: str = "pending", content: str = "hello world") -> MagicMock:
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.business_id = uuid.uuid4()
    doc.status = status
    doc.content = content
    doc.embedding = None
    doc.error_message = None
    return doc


async def test_failure_sets_status_failed_not_error(fake_session: MagicMock) -> None:
    """Embedding API failure must write 'failed', not the rejected 'error'."""
    doc = _make_doc()
    fake_session.get.return_value = doc

    with (
        patch.object(knowledge_tasks, "chunk_text", return_value=["chunk-a"]),
        patch.object(knowledge_tasks, "embed_texts", new=AsyncMock(side_effect=RuntimeError("boom"))),
        pytest.raises(RuntimeError),
    ):
        await _run_with_session(fake_session, doc.id)

    assert doc.status == "failed"
    assert doc.status != "error"
    assert doc.error_message == "boom"
    fake_session.commit.assert_awaited()


async def test_failed_documents_are_eligible_for_reembed(fake_session: MagicMock) -> None:
    """The re-embed gate must accept 'failed' (the canonical name) for retries."""
    doc = _make_doc(status="failed", content="")
    fake_session.get.return_value = doc

    with patch.object(knowledge_tasks, "chunk_text", return_value=[]):
        await _run_with_session(fake_session, doc.id)

    # Empty-content branch ran → status flipped to ready, proving the gate let
    # a 'failed' doc through.
    assert doc.status == "ready"


async def test_legacy_error_status_is_not_accepted_by_gate(fake_session: MagicMock) -> None:
    """A doc still tagged 'error' (legacy/unmigrated row) is skipped, not retried.

    Pins the intentional break: post-migration the only retryable bad state is
    'failed'. A stray 'error' should NOT be silently picked up.
    """
    doc = _make_doc(status="error")
    fake_session.get.return_value = doc

    with patch.object(knowledge_tasks, "chunk_text") as chunk_mock:
        await _run_with_session(fake_session, doc.id)

    chunk_mock.assert_not_called()
    assert doc.status == "error"  # untouched — gate returned early


async def test_happy_path_sets_status_ready(fake_session: MagicMock) -> None:
    doc = _make_doc()
    fake_session.get.return_value = doc

    with (
        patch.object(knowledge_tasks, "chunk_text", return_value=["a", "b"]),
        patch.object(
            knowledge_tasks,
            "embed_texts",
            new=AsyncMock(return_value=[[0.1] * 1536, [0.2] * 1536]),
        ),
    ):
        await _run_with_session(fake_session, doc.id)

    assert doc.status == "ready"
    assert doc.error_message is None


def test_worker_source_has_no_error_status_writes() -> None:
    """Belt-and-braces: grep the worker source for any 'error' status assignment."""
    import inspect

    src = inspect.getsource(knowledge_tasks)
    assert 'status = "error"' not in src
    assert "status = 'error'" not in src
