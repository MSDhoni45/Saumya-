import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# `timestamptz` in the migrations — see app/models/whatsapp.py for why this
# must be timezone-aware (asyncpg rejects naive/aware datetime mismatches).
_TZ_DATETIME = DateTime(timezone=True)
_EMBEDDING_DIM = 1536


class AiAgent(Base):
    __tablename__ = "ai_agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    agent_type: Mapped[str] = mapped_column(String, nullable=False, default="sales")
    persona: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="openai")
    model: Mapped[str] = mapped_column(String, nullable=False, default="gpt-4o-mini")
    temperature: Mapped[float] = mapped_column(Numeric(2, 1), nullable=False, default=0.4)
    qualification_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    interactions: Mapped[list["AiInteraction"]] = relationship(back_populates="agent")


class AiInteraction(Base):
    __tablename__ = "ai_interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    inbound_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    outbound_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    retrieved_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    extracted_lead_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    agent: Mapped["AiAgent"] = relationship(back_populates="interactions")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    documents: Mapped[list["Document"]] = relationship(back_populates="knowledge_base")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False, default="text")
    source_url: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIM))
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index"
    )


class DocumentChunk(Base):
    """Token-bounded slice of `Document.content` with its own embedding vector.

    RAG retrieval queries this table directly so similarity search returns the
    exact passage the model should ground on, instead of a single embedding
    representing a truncated whole document.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIM))
    token_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    name: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    budget: Mapped[str | None] = mapped_column(Text)
    service_interested: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String, nullable=False, default="new")
    source: Mapped[str] = mapped_column(String, nullable=False, default="whatsapp")
    # AI-extracted qualification blob — accumulates freetext from the agent
    # pipeline. Manual agent notes go in LeadNote (separate table with author
    # attribution and delete capability).
    notes: Mapped[str | None] = mapped_column(Text)
    stage_changed_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    lead_notes: Mapped[list["LeadNote"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="LeadNote.created_at.desc()"
    )
    events: Mapped[list["LeadEvent"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="LeadEvent.created_at.asc()"
    )


class LeadNote(Base):
    """Manual notes written by agents against a lead.

    Kept separate from `Lead.notes` (the AI qualification blob) so notes have
    author attribution, timestamps, and can be individually deleted without
    touching the AI-extracted data the sales pipeline depends on.
    """

    __tablename__ = "lead_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # null = AI/system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="lead_notes")


class OperatorAlert(Base):
    """Operator-visible record of an automated-pipeline failure.

    Created when the agent path cannot finish a turn (WhatsApp send error,
    terminal `failed` status callback). Separate from system messages because
    alerts need acknowledgement state and a dedicated inbox.
    """

    __tablename__ = "operator_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    acknowledged_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class LeadEvent(Base):
    """Append-only timeline journal for a lead.

    Every significant change (stage transition, note, field update, assignment)
    writes one row here. The `payload` JSONB is typed per `event_type` — see
    the router/service layer for the canonical shapes. New event types never
    require a schema migration; only a new frontend renderer.
    """

    __tablename__ = "lead_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # null = AI/system
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="events")
