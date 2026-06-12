import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, cast

import anthropic
import openai
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from app.core.config import settings
from app.schemas.agent import StructuredAgentReply

logger = logging.getLogger(__name__)

# The model is asked to always respond with one JSON object matching this
# shape — this is what makes the orchestration provider-agnostic: callers get
# back the same `StructuredAgentReply` regardless of which vendor answered.
_RESPONSE_INSTRUCTIONS = """
Always respond with a single JSON object — no prose outside it — matching exactly:
{
  "reply": "<the message to send back to the contact, in their language, concise and natural>",
  "extracted_lead_fields": {"<field_key>": "<value volunteered THIS turn only>", ...},
  "lead_name": "<full name if volunteered this turn, else null>",
  "lead_email": "<email if volunteered this turn, else null>",
  "lead_phone": "<phone number if volunteered this turn, else null>"
}
Only include a key in "extracted_lead_fields" when the contact clearly stated
that value in their latest message — never guess, infer, or repeat values you
already have. "reply" must always be present and non-empty.
""".strip()

_OPENAI_JSON_SCHEMA: dict[str, Any] = {
    "name": "agent_reply",
    "schema": {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "extracted_lead_fields": {"type": "object", "additionalProperties": {"type": "string"}},
            "lead_name": {"type": ["string", "null"]},
            "lead_email": {"type": ["string", "null"]},
            "lead_phone": {"type": ["string", "null"]},
        },
        "required": ["reply", "extracted_lead_fields", "lead_name", "lead_email", "lead_phone"],
        "additionalProperties": False,
    },
    "strict": True,
}


@dataclass(frozen=True, slots=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    structured: StructuredAgentReply
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


class LlmProviderError(RuntimeError):
    """Non-retryable provider failure (e.g. bad JSON, schema mismatch)."""


def _is_retryable_openai(exc: BaseException) -> bool:
    """429, 5xx, network/timeout — anything where a retry could plausibly help.

    `APIStatusError` covers all non-2xx; filter to 5xx so we don't burn retries
    on a 400 (bad request) or 401 (auth) — those won't recover.
    """
    if isinstance(exc, (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError)):
        return True
    if isinstance(exc, openai.APIStatusError):
        status = getattr(exc, "status_code", None)
        return status is not None and 500 <= status < 600
    return False


def _is_retryable_anthropic(exc: BaseException) -> bool:
    if isinstance(
        exc, (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APITimeoutError)
    ):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        status = getattr(exc, "status_code", None)
        return status is not None and 500 <= status < 600
    return False


# 3 attempts, exponential backoff with jitter (tenacity's wait_random_exponential
# picks uniformly in [0, min(multiplier*2**attempt, max)]). Bounded so a bad
# upstream doesn't hold a worker for minutes.
_OPENAI_RETRY = retry(
    retry=retry_if_exception(_is_retryable_openai),
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=8),
    reraise=True,
)
_ANTHROPIC_RETRY = retry(
    retry=retry_if_exception(_is_retryable_anthropic),
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=8),
    reraise=True,
)


@lru_cache
def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


@lru_cache
def _anthropic_client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


def _parse_structured_reply(raw: str) -> StructuredAgentReply:
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise LlmProviderError(f"Provider returned non-JSON output: {raw!r}") from exc

    try:
        return StructuredAgentReply.model_validate(payload)
    except Exception as exc:
        raise LlmProviderError(f"Provider JSON did not match the expected reply shape: {payload!r}") from exc


@_OPENAI_RETRY
async def _complete_openai(
    *, system_prompt: str, history: list[ChatTurn], model: str, temperature: float
) -> LlmCompletion:
    started = time.monotonic()
    messages = cast(
        "list[ChatCompletionMessageParam]",
        [
            {"role": "system", "content": f"{system_prompt}\n\n{_RESPONSE_INSTRUCTIONS}"},
            *[{"role": turn.role, "content": turn.content} for turn in history],
        ],
    )
    response = await _openai_client().chat.completions.create(
        model=model,
        temperature=temperature,
        messages=messages,
        response_format=cast(Any, {"type": "json_schema", "json_schema": _OPENAI_JSON_SCHEMA}),
    )
    latency_ms = int((time.monotonic() - started) * 1000)

    choice = response.choices[0]
    structured = _parse_structured_reply(choice.message.content or "")
    usage = response.usage
    return LlmCompletion(
        structured=structured,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        latency_ms=latency_ms,
    )


@_ANTHROPIC_RETRY
async def _complete_anthropic(
    *, system_prompt: str, history: list[ChatTurn], model: str, temperature: float
) -> LlmCompletion:
    started = time.monotonic()
    messages = cast("list[MessageParam]", [{"role": turn.role, "content": turn.content} for turn in history])
    response = await _anthropic_client().messages.create(
        model=model,
        max_tokens=1024,
        temperature=temperature,
        system=f"{system_prompt}\n\n{_RESPONSE_INSTRUCTIONS}",
        messages=messages,
    )
    latency_ms = int((time.monotonic() - started) * 1000)

    text_blocks = [block.text for block in response.content if block.type == "text"]
    structured = _parse_structured_reply("".join(text_blocks))
    return LlmCompletion(
        structured=structured,
        prompt_tokens=response.usage.input_tokens if response.usage else None,
        completion_tokens=response.usage.output_tokens if response.usage else None,
        latency_ms=latency_ms,
    )


async def generate_structured_reply(
    *, provider: str, model: str, temperature: float, system_prompt: str, history: list[ChatTurn]
) -> LlmCompletion:
    """Provider-agnostic structured chat completion.

    Returns a normalized `LlmCompletion` regardless of whether `provider` is
    "openai" or "anthropic" — orchestration code never needs to branch on it.

    Resilience: each provider call retries up to 3× on retryable errors
    (429 / 5xx / network / timeout) with exponential jittered backoff. When
    `settings.llm_fallback_enabled` is on and the primary provider still
    raises a retryable error after exhaustion, the call is retried once
    against the other provider using the configured fallback model. This is
    the last line of defence — `LlmProviderError` (bad JSON / schema) is
    never retried because it is deterministic.
    """
    if provider not in ("openai", "anthropic"):
        raise LlmProviderError(f"Unsupported AI provider: {provider!r}")

    try:
        return await _call_provider(
            provider=provider,
            model=model,
            temperature=temperature,
            system_prompt=system_prompt,
            history=history,
        )
    except Exception as exc:
        if not settings.llm_fallback_enabled:
            raise
        if not _is_fallback_eligible(provider, exc):
            raise
        fallback_provider = "anthropic" if provider == "openai" else "openai"
        fallback_model = (
            settings.fallback_anthropic_model
            if fallback_provider == "anthropic"
            else settings.fallback_openai_model
        )
        logger.warning(
            "LLM primary provider=%s exhausted on %s — falling back to provider=%s model=%s",
            provider,
            type(exc).__name__,
            fallback_provider,
            fallback_model,
        )
        return await _call_provider(
            provider=fallback_provider,
            model=fallback_model,
            temperature=temperature,
            system_prompt=system_prompt,
            history=history,
        )


async def _call_provider(
    *, provider: str, model: str, temperature: float, system_prompt: str, history: list[ChatTurn]
) -> LlmCompletion:
    if provider == "openai":
        return await _complete_openai(
            system_prompt=system_prompt, history=history, model=model, temperature=temperature
        )
    return await _complete_anthropic(
        system_prompt=system_prompt, history=history, model=model, temperature=temperature
    )


def _is_fallback_eligible(provider: str, exc: BaseException) -> bool:
    """Only fall back on the same class of errors we retried for.

    A non-retryable error (auth, bad request, JSON parse) means the *call*
    was wrong, not the provider — falling over to the other vendor would
    just produce the same failure or mask a real bug.
    """
    if provider == "openai":
        return _is_retryable_openai(exc)
    return _is_retryable_anthropic(exc)
