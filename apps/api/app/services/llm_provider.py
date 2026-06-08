import json
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, cast

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.schemas.agent import StructuredAgentReply

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
    pass


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


@retry(
    retry=retry_if_exception_type((LlmProviderError, TimeoutError)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
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


@retry(
    retry=retry_if_exception_type((LlmProviderError, TimeoutError)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
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
    """
    if provider == "openai":
        return await _complete_openai(system_prompt=system_prompt, history=history, model=model, temperature=temperature)
    if provider == "anthropic":
        return await _complete_anthropic(
            system_prompt=system_prompt, history=history, model=model, temperature=temperature
        )
    raise LlmProviderError(f"Unsupported AI provider: {provider!r}")
