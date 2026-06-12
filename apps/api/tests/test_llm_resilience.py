"""Tests for LLM provider resilience: retry + cross-provider fallback.

Covers Phase B P3:
- 429 / 5xx / network errors are retried (3 attempts, jittered backoff)
- Non-retryable errors (bad JSON, 4xx auth) fail fast
- Cross-provider fallback fires only when LLM_FALLBACK_ENABLED is True
  AND the failure was retryable
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import openai
import pytest

from app.core.config import settings
from app.services import llm_provider
from app.services.llm_provider import (
    ChatTurn,
    LlmCompletion,
    LlmProviderError,
    generate_structured_reply,
)


_VALID_REPLY_JSON = json.dumps(
    {
        "reply": "hello there",
        "extracted_lead_fields": {},
        "lead_name": None,
        "lead_email": None,
        "lead_phone": None,
    }
)


def _openai_response() -> MagicMock:
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = _VALID_REPLY_JSON
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    return response


def _anthropic_response() -> MagicMock:
    response = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = _VALID_REPLY_JSON
    response.content = [block]
    response.usage = MagicMock(input_tokens=10, output_tokens=5)
    return response


def _openai_rate_limit() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


def _openai_5xx() -> openai.APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(503, request=request)
    return openai.APIStatusError("server error", response=response, body=None)


def _openai_4xx() -> openai.APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return openai.APIStatusError("bad request", response=response, body=None)


def _openai_network() -> openai.APIConnectionError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.APIConnectionError(request=request)


def _anthropic_rate_limit() -> anthropic.RateLimitError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, request=request)
    return anthropic.RateLimitError("rate limited", response=response, body=None)


def _anthropic_5xx() -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(503, request=request)
    return anthropic.APIStatusError("server error", response=response, body=None)


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    """Strip backoff so tests don't actually sleep on retry."""
    from tenacity import wait_none

    for fn in (llm_provider._complete_openai, llm_provider._complete_anthropic):
        if hasattr(fn, "retry"):
            fn.retry.wait = wait_none()
    yield


@pytest.fixture
def common():
    return {
        "system_prompt": "you are a sales agent",
        "history": [ChatTurn(role="user", content="hi")],
        "temperature": 0.2,
    }


@pytest.fixture(autouse=True)
def _disable_fallback_by_default():
    original = settings.llm_fallback_enabled
    settings.llm_fallback_enabled = False
    yield
    settings.llm_fallback_enabled = original


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


async def test_openai_429_is_retried_then_succeeds(common):
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=[_openai_rate_limit(), _openai_response()])
    llm_provider._openai_client.cache_clear()
    with patch.object(llm_provider, "_openai_client", return_value=client):
        result = await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    assert isinstance(result, LlmCompletion)
    assert client.chat.completions.create.await_count == 2


async def test_openai_5xx_is_retried_then_succeeds(common):
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=[_openai_5xx(), _openai_response()])
    with patch.object(llm_provider, "_openai_client", return_value=client):
        result = await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    assert isinstance(result, LlmCompletion)
    assert client.chat.completions.create.await_count == 2


async def test_openai_network_error_is_retried_then_succeeds(common):
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=[_openai_network(), _openai_response()])
    with patch.object(llm_provider, "_openai_client", return_value=client):
        result = await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    assert isinstance(result, LlmCompletion)
    assert client.chat.completions.create.await_count == 2


async def test_openai_4xx_is_not_retried(common):
    """Non-5xx APIStatusError must fail fast — retries can't fix auth/bad-input."""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=_openai_4xx())
    with patch.object(llm_provider, "_openai_client", return_value=client):
        with pytest.raises(openai.APIStatusError):
            await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    assert client.chat.completions.create.await_count == 1


async def test_openai_exhausts_three_attempts_then_raises(common):
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=[_openai_rate_limit()] * 3)
    with patch.object(llm_provider, "_openai_client", return_value=client):
        with pytest.raises(openai.RateLimitError):
            await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    assert client.chat.completions.create.await_count == 3


async def test_bad_json_is_not_retried(common):
    """LlmProviderError (deterministic) must not retry — provider would keep failing."""
    response = _openai_response()
    response.choices[0].message.content = "not json at all"
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    with patch.object(llm_provider, "_openai_client", return_value=client):
        with pytest.raises(LlmProviderError):
            await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    assert client.chat.completions.create.await_count == 1


async def test_anthropic_429_is_retried_then_succeeds(common):
    client = AsyncMock()
    client.messages.create = AsyncMock(side_effect=[_anthropic_rate_limit(), _anthropic_response()])
    with patch.object(llm_provider, "_anthropic_client", return_value=client):
        result = await generate_structured_reply(provider="anthropic", model="claude-sonnet-4-5", **common)

    assert isinstance(result, LlmCompletion)
    assert client.messages.create.await_count == 2


# ---------------------------------------------------------------------------
# Cross-provider fallback (LLM_FALLBACK_ENABLED)
# ---------------------------------------------------------------------------


async def test_no_fallback_when_flag_is_off(common):
    settings.llm_fallback_enabled = False
    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(side_effect=[_openai_rate_limit()] * 3)
    anthropic_client = AsyncMock()
    anthropic_client.messages.create = AsyncMock()

    with (
        patch.object(llm_provider, "_openai_client", return_value=openai_client),
        patch.object(llm_provider, "_anthropic_client", return_value=anthropic_client),
    ):
        with pytest.raises(openai.RateLimitError):
            await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    anthropic_client.messages.create.assert_not_awaited()


async def test_fallback_openai_to_anthropic_when_enabled(common):
    settings.llm_fallback_enabled = True
    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(side_effect=[_openai_rate_limit()] * 3)
    anthropic_client = AsyncMock()
    anthropic_client.messages.create = AsyncMock(return_value=_anthropic_response())

    with (
        patch.object(llm_provider, "_openai_client", return_value=openai_client),
        patch.object(llm_provider, "_anthropic_client", return_value=anthropic_client),
    ):
        result = await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    assert isinstance(result, LlmCompletion)
    assert openai_client.chat.completions.create.await_count == 3
    anthropic_client.messages.create.assert_awaited_once()
    # Fallback must use the configured fallback model, not the original.
    kwargs = anthropic_client.messages.create.await_args.kwargs
    assert kwargs["model"] == settings.fallback_anthropic_model


async def test_fallback_anthropic_to_openai_when_enabled(common):
    settings.llm_fallback_enabled = True
    anthropic_client = AsyncMock()
    anthropic_client.messages.create = AsyncMock(side_effect=[_anthropic_5xx()] * 3)
    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(return_value=_openai_response())

    with (
        patch.object(llm_provider, "_anthropic_client", return_value=anthropic_client),
        patch.object(llm_provider, "_openai_client", return_value=openai_client),
    ):
        result = await generate_structured_reply(
            provider="anthropic", model="claude-sonnet-4-5", **common
        )

    assert isinstance(result, LlmCompletion)
    assert anthropic_client.messages.create.await_count == 3
    openai_client.chat.completions.create.assert_awaited_once()
    kwargs = openai_client.chat.completions.create.await_args.kwargs
    assert kwargs["model"] == settings.fallback_openai_model


async def test_fallback_does_not_fire_on_non_retryable(common):
    """Fallback is for transient infra failures, not bad-input/auth errors."""
    settings.llm_fallback_enabled = True
    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(side_effect=_openai_4xx())
    anthropic_client = AsyncMock()
    anthropic_client.messages.create = AsyncMock()

    with (
        patch.object(llm_provider, "_openai_client", return_value=openai_client),
        patch.object(llm_provider, "_anthropic_client", return_value=anthropic_client),
    ):
        with pytest.raises(openai.APIStatusError):
            await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    anthropic_client.messages.create.assert_not_awaited()


async def test_fallback_does_not_fire_on_bad_json(common):
    settings.llm_fallback_enabled = True
    response = _openai_response()
    response.choices[0].message.content = "not json"
    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(return_value=response)
    anthropic_client = AsyncMock()
    anthropic_client.messages.create = AsyncMock()

    with (
        patch.object(llm_provider, "_openai_client", return_value=openai_client),
        patch.object(llm_provider, "_anthropic_client", return_value=anthropic_client),
    ):
        with pytest.raises(LlmProviderError):
            await generate_structured_reply(provider="openai", model="gpt-4o", **common)

    anthropic_client.messages.create.assert_not_awaited()


async def test_unsupported_provider_raises_immediately(common):
    with pytest.raises(LlmProviderError):
        await generate_structured_reply(provider="cohere", model="x", **common)
