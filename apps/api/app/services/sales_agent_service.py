import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AiAgent, AiInteraction
from app.models.whatsapp import Conversation, Message
from app.services.lead_service import apply_extracted_fields, get_or_create_lead, known_qualification_values
from app.services.llm_provider import ChatTurn, generate_structured_reply
from app.services.rag_service import RetrievedChunk, format_chunks_for_prompt, retrieve_relevant_chunks

# How many prior turns to include verbatim — enough for the model to track the
# qualification conversation without ballooning prompt size/cost on long threads.
_HISTORY_TURNS = 12

_DEFAULT_SALES_PERSONA = (
    "You are a friendly, knowledgeable sales assistant. Be concise, helpful, "
    "and never invent facts about the business."
)


@dataclass(frozen=True, slots=True)
class AgentReplyResult:
    reply: str
    extracted_lead_fields: dict[str, str]
    retrieved_chunks: list[RetrievedChunk]
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


async def get_active_agent(
    session: AsyncSession, *, business_id: uuid.UUID, agent_type: str = "sales"
) -> AiAgent | None:
    stmt = (
        select(AiAgent)
        .where(AiAgent.business_id == business_id, AiAgent.agent_type == agent_type, AiAgent.is_active.is_(True))
        .order_by(AiAgent.created_at)
        .limit(1)
    )
    return await session.scalar(stmt)


def _build_system_prompt(
    *, agent: AiAgent, retrieved_chunks: list[RetrievedChunk], known_fields: dict[str, str], outstanding: list[dict]
) -> str:
    persona = agent.persona or _DEFAULT_SALES_PERSONA

    sections = [persona, "\n--- Business knowledge (only use facts from here; never invent details) ---",
                format_chunks_for_prompt(retrieved_chunks)]

    if outstanding:
        wanted = "\n".join(
            f"- {field['key']}: {field['label']}" + (" (required)" if field.get("required") else "")
            for field in outstanding
        )
        sections.append(
            "\n--- Lead qualification ---\n"
            "Naturally work these details into the conversation, one at a time, "
            "without interrogating the contact:\n" + wanted
        )

    if known_fields:
        sections.append(
            "\n--- Already known about this contact (do NOT ask again) ---\n"
            + "\n".join(f"- {key}: {value}" for key, value in known_fields.items())
        )

    return "\n".join(sections)


def _build_history(messages: list[Message], *, latest_inbound_id: uuid.UUID) -> list[ChatTurn]:
    relevant = [m for m in messages if m.id != latest_inbound_id and m.content][-_HISTORY_TURNS:]
    history = [
        ChatTurn(role="assistant" if m.direction == "outbound" else "user", content=m.content or "")
        for m in relevant
    ]
    return history


async def generate_agent_reply(
    session: AsyncSession,
    *,
    agent: AiAgent,
    conversation: Conversation,
    inbound_message: Message,
    history_messages: list[Message],
) -> AgentReplyResult:
    """Run one full sales-agent turn: retrieve context, ask the LLM, capture the lead.

    This is the seam the Celery task and the `/test` sandbox endpoint both call
    through — keeping "what happens on a turn" in exactly one place.
    """
    qualification_fields: list[dict] = list(agent.qualification_fields or [])
    qualification_keys = {f["key"] for f in qualification_fields if "key" in f}

    lead = await get_or_create_lead(
        session,
        business_id=agent.business_id,
        conversation_id=conversation.id,
        contact_phone=conversation.contact_phone,
        contact_name=conversation.contact_name,
    )
    known_fields = known_qualification_values(lead, qualification_keys)
    outstanding = [f for f in qualification_fields if f.get("key") not in known_fields]

    query = inbound_message.content or ""
    retrieved_chunks = await retrieve_relevant_chunks(session, business_id=agent.business_id, query=query) if query else []

    system_prompt = _build_system_prompt(
        agent=agent, retrieved_chunks=retrieved_chunks, known_fields=known_fields, outstanding=outstanding
    )
    history = _build_history(history_messages, latest_inbound_id=inbound_message.id)
    history.append(ChatTurn(role="user", content=query))

    completion = await generate_structured_reply(
        provider=agent.provider,
        model=agent.model,
        temperature=float(agent.temperature),
        system_prompt=system_prompt,
        history=history,
    )

    applied_fields = apply_extracted_fields(lead, completion.structured, qualification_keys)

    return AgentReplyResult(
        reply=completion.structured.reply,
        extracted_lead_fields=applied_fields,
        retrieved_chunks=retrieved_chunks,
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        latency_ms=completion.latency_ms,
    )


async def reserve_interaction(
    session: AsyncSession,
    *,
    agent: AiAgent,
    conversation_id: uuid.UUID,
    inbound_message_id: uuid.UUID,
) -> uuid.UUID | None:
    """Reserve an `ai_interactions` row for this inbound message.

    Returns the new interaction id on success, or `None` if a row for this
    `inbound_message_id` already exists. The caller MUST commit immediately
    after a successful reservation so a concurrent retry (Celery, parallel
    worker) sees the marker and short-circuits before calling the LLM or
    sending a WhatsApp message.

    The `ux_ai_interactions_inbound_message_id` UNIQUE constraint (see
    migration 20260612000001) is what makes the ON CONFLICT race-safe.
    Without it, two simultaneous INSERTs could both succeed.
    """
    result = await session.execute(
        text("""
            INSERT INTO ai_interactions (
                id, business_id, agent_id, conversation_id, inbound_message_id,
                provider, model, retrieved_chunk_ids, extracted_lead_fields
            ) VALUES (
                gen_random_uuid(), :bid, :aid, :cid, :imid,
                :provider, :model, ARRAY[]::uuid[], '{}'::jsonb
            )
            ON CONFLICT (inbound_message_id) DO NOTHING
            RETURNING id
        """),
        {
            "bid": agent.business_id,
            "aid": agent.id,
            "cid": conversation_id,
            "imid": inbound_message_id,
            "provider": agent.provider,
            "model": agent.model,
        },
    )
    row = result.fetchone()
    return row[0] if row else None


async def finalize_interaction(
    session: AsyncSession,
    *,
    interaction_id: uuid.UUID,
    outbound_message_id: uuid.UUID,
    result: AgentReplyResult,
) -> None:
    """Fill in tokens / latency / chunks / extracted fields on a reserved row.

    Paired with `reserve_interaction`: the row already exists (with provider
    + model recorded at reservation time); this just attaches the post-send
    audit data. No new row is created — preserves the one-inbound-one-reply
    invariant the UNIQUE constraint enforces.
    """
    interaction = await session.get(AiInteraction, interaction_id)
    if interaction is None:
        # Reservation row vanished between reserve and finalize — should not
        # happen in practice (no caller deletes interactions), but logging
        # is better than a silent no-op.
        raise RuntimeError(f"Reserved AiInteraction {interaction_id} disappeared before finalize")
    interaction.outbound_message_id = outbound_message_id
    interaction.prompt_tokens = result.prompt_tokens
    interaction.completion_tokens = result.completion_tokens
    interaction.latency_ms = result.latency_ms
    interaction.retrieved_chunk_ids = [chunk.chunk_id for chunk in result.retrieved_chunks]
    interaction.extracted_lead_fields = result.extracted_lead_fields
    await session.flush()


async def record_interaction(
    session: AsyncSession,
    *,
    agent: AiAgent,
    conversation_id: uuid.UUID,
    inbound_message_id: uuid.UUID | None,
    outbound_message_id: uuid.UUID | None,
    result: AgentReplyResult,
) -> AiInteraction:
    """Persist the audit trail row — what we said, why, and what we learned."""
    interaction = AiInteraction(
        business_id=agent.business_id,
        agent_id=agent.id,
        conversation_id=conversation_id,
        inbound_message_id=inbound_message_id,
        outbound_message_id=outbound_message_id,
        provider=agent.provider,
        model=agent.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_ms=result.latency_ms,
        retrieved_chunk_ids=[chunk.chunk_id for chunk in result.retrieved_chunks],
        extracted_lead_fields=result.extracted_lead_fields,
    )
    session.add(interaction)
    await session.flush()
    return interaction
