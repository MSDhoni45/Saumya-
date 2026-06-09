import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BusinessContext, get_current_business, require_business_access
from app.db.session import get_db_session
from app.models.agent import AiAgent, AiInteraction
from app.schemas.agent import (
    AgentTestRequest,
    AgentTestResponse,
    AiAgentCreateRequest,
    AiAgentResponse,
    AiAgentUpdateRequest,
    AiInteractionResponse,
    RetrievedChunk,
)
from app.services.llm_provider import ChatTurn as LlmChatTurn
from app.services.llm_provider import generate_structured_reply
from app.services.rag_service import retrieve_relevant_chunks

router = APIRouter(prefix="/agents", tags=["agents"])

_DEFAULT_PERSONA = (
    "You are a friendly, knowledgeable sales assistant. Be concise, helpful, "
    "and never invent facts about the business."
)


@router.post("/{business_id}", response_model=AiAgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    business_id: uuid.UUID,
    payload: AiAgentCreateRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> AiAgent:
    require_business_access(ctx, business_id)
    agent = AiAgent(
        business_id=business_id,
        name=payload.name,
        agent_type=payload.agent_type,
        persona=payload.persona or _DEFAULT_PERSONA,
        provider=payload.provider,
        model=payload.model,
        temperature=payload.temperature,
        qualification_fields=[f.model_dump() for f in payload.qualification_fields],
        is_active=payload.is_active,
    )
    session.add(agent)
    await session.flush()
    await session.refresh(agent)
    return agent


@router.get("/{business_id}", response_model=list[AiAgentResponse])
async def list_agents(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[AiAgent]:
    require_business_access(ctx, business_id)
    stmt = select(AiAgent).where(AiAgent.business_id == business_id).order_by(AiAgent.created_at)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{business_id}/{agent_id}", response_model=AiAgentResponse)
async def get_agent(
    business_id: uuid.UUID,
    agent_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> AiAgent:
    require_business_access(ctx, business_id)
    return await _get_agent_or_404(session, business_id, agent_id)


@router.patch("/{business_id}/{agent_id}", response_model=AiAgentResponse)
async def update_agent(
    business_id: uuid.UUID,
    agent_id: uuid.UUID,
    payload: AiAgentUpdateRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> AiAgent:
    require_business_access(ctx, business_id)
    agent = await _get_agent_or_404(session, business_id, agent_id)

    updates = payload.model_dump(exclude_unset=True)
    if payload.qualification_fields is not None:
        updates["qualification_fields"] = [f.model_dump() for f in payload.qualification_fields]
    for field, value in updates.items():
        setattr(agent, field, value)

    await session.flush()
    await session.refresh(agent)
    return agent


@router.delete("/{business_id}/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    business_id: uuid.UUID,
    agent_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    require_business_access(ctx, business_id)
    agent = await _get_agent_or_404(session, business_id, agent_id)
    await session.delete(agent)


@router.get("/{business_id}/{agent_id}/interactions", response_model=list[AiInteractionResponse])
async def list_agent_interactions(
    business_id: uuid.UUID,
    agent_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[AiInteraction]:
    require_business_access(ctx, business_id)
    await _get_agent_or_404(session, business_id, agent_id)
    stmt = (
        select(AiInteraction)
        .where(AiInteraction.business_id == business_id, AiInteraction.agent_id == agent_id)
        .order_by(AiInteraction.created_at.desc())
        .limit(50)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("/{business_id}/{agent_id}/test", response_model=AgentTestResponse)
async def test_agent(
    business_id: uuid.UUID,
    agent_id: uuid.UUID,
    payload: AgentTestRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> AgentTestResponse:
    """Sandbox endpoint: run a single turn against the agent without touching
    real conversations/leads/WhatsApp — lets a business owner tune persona,
    qualification fields, and knowledge base before going live.
    """
    require_business_access(ctx, business_id)
    agent = await _get_agent_or_404(session, business_id, agent_id)

    qualification_fields: list[dict] = list(agent.qualification_fields or [])
    qualification_keys = {f["key"] for f in qualification_fields if "key" in f}
    outstanding = [f for f in qualification_fields if f.get("key") not in payload.known_lead_fields]

    retrieved_chunks = await retrieve_relevant_chunks(session, business_id=business_id, query=payload.message)

    sections = [
        agent.persona or _DEFAULT_PERSONA,
        "\n--- Business knowledge (only use facts from here; never invent details) ---",
        "\n\n".join(f"[{i}] {c.title}\n{c.content}" for i, c in enumerate(retrieved_chunks, start=1))
        or "No relevant business documents were found for this query.",
    ]
    if outstanding:
        wanted = "\n".join(f"- {f['key']}: {f['label']}" for f in outstanding)
        sections.append(
            "\n--- Lead qualification ---\n"
            "Naturally work these details into the conversation, one at a time:\n" + wanted
        )
    if payload.known_lead_fields:
        sections.append(
            "\n--- Already known about this contact (do NOT ask again) ---\n"
            + "\n".join(f"- {k}: {v}" for k, v in payload.known_lead_fields.items())
        )

    history = [LlmChatTurn(role=turn.role, content=turn.content) for turn in payload.history]
    history.append(LlmChatTurn(role="user", content=payload.message))

    completion = await generate_structured_reply(
        provider=agent.provider,
        model=agent.model,
        temperature=float(agent.temperature),
        system_prompt="\n".join(sections),
        history=history,
    )

    extracted = {
        key: value
        for key, value in completion.structured.extracted_lead_fields.items()
        if key in qualification_keys and value
    }

    return AgentTestResponse(
        reply=completion.structured.reply,
        extracted_lead_fields=extracted,
        retrieved_chunks=[
            RetrievedChunk(document_id=c.document_id, title=c.title, content=c.content, similarity=c.similarity)
            for c in retrieved_chunks
        ],
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        latency_ms=completion.latency_ms,
    )


async def _get_agent_or_404(session: AsyncSession, business_id: uuid.UUID, agent_id: uuid.UUID) -> AiAgent:
    agent = await session.get(AiAgent, agent_id)
    if agent is None or agent.business_id != business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent
