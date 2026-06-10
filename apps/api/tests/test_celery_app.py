"""Unit tests for app/workers/celery_app.py — Sentry wiring and failure logging."""

import logging
from unittest.mock import MagicMock, patch

from app.workers.celery_app import _init_sentry, _log_task_failure


def test_task_failure_logs_error(caplog):
    sender = MagicMock()
    sender.name = "agents.generate_reply"
    exc = RuntimeError("LLM timeout")

    with caplog.at_level(logging.ERROR, logger="app.workers.celery_app"):
        _log_task_failure(task_id="abc-123", exception=exc, sender=sender)

    assert "agents.generate_reply" in caplog.text
    assert "abc-123" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "LLM timeout" in caplog.text


def test_task_failure_handles_missing_fields(caplog):
    with caplog.at_level(logging.ERROR, logger="app.workers.celery_app"):
        _log_task_failure()
    assert "unknown" in caplog.text


def test_sentry_not_initialized_without_dsn():
    with (
        patch("app.workers.celery_app.settings") as mock_settings,
        patch("sentry_sdk.init") as mock_init,
    ):
        mock_settings.sentry_dsn = None
        _init_sentry()
    mock_init.assert_not_called()


def test_sentry_initialized_with_dsn():
    with (
        patch("app.workers.celery_app.settings") as mock_settings,
        patch("sentry_sdk.init") as mock_init,
    ):
        mock_settings.sentry_dsn = "https://key@sentry.example/1"
        mock_settings.sentry_traces_sample_rate = 0.1
        mock_settings.environment = "test"
        _init_sentry()

    mock_init.assert_called_once()
    kwargs = mock_init.call_args.kwargs
    assert kwargs["dsn"] == "https://key@sentry.example/1"
    assert kwargs["send_default_pii"] is False
    assert any(type(i).__name__ == "CeleryIntegration" for i in kwargs["integrations"])
