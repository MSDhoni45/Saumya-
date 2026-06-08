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
    notes: Mapped[str | None] = mapped_column(Text)
    stage_changed_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
