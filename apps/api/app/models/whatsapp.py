import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User

# All timestamp columns are `timestamptz` in the migrations — map to
# timezone-aware `DateTime` so asyncpg doesn't reject offset-aware Python
# datetimes (e.g. `datetime.now(tz=timezone.utc)`) with a naive/aware mismatch.
_TZ_DATETIME = DateTime(timezone=True)


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str | None] = mapped_column(String)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="UTC")
    onboarding_completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    notify_whatsapp_phone: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    whatsapp_accounts: Mapped[list["WhatsAppAccount"]] = relationship(back_populates="business")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="business")
    users: Mapped[list["User"]] = relationship(back_populates="business")


class WhatsAppAccount(Base):
    __tablename__ = "whatsapp_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    waba_id: Mapped[str] = mapped_column(String, nullable=False)
    phone_number_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    access_token: Mapped[str | None] = mapped_column(Text)  # encrypted at rest — see services/encryption
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    connected_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    business: Mapped["Business"] = relationship(back_populates="whatsapp_accounts")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="whatsapp_account")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    whatsapp_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("whatsapp_accounts.id", ondelete="CASCADE"), nullable=False
    )
    contact_phone: Mapped[str] = mapped_column(String, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    last_message_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    business: Mapped["Business"] = relationship(back_populates="conversations")
    whatsapp_account: Mapped["WhatsAppAccount"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String, nullable=False)  # inbound | outbound
    sender_type: Mapped[str] = mapped_column(String, nullable=False)  # contact | ai | agent | system
    message_type: Mapped[str] = mapped_column(String, nullable=False, default="text")
    content: Mapped[str | None] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(Text)
    whatsapp_message_id: Mapped[str | None] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="sent")
    # Meta callback timestamps — populated as the message walks the
    # sent → delivered → read state machine (or terminates at failed).
    delivered_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    read_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    failed_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    error_code: Mapped[str | None] = mapped_column(String)
    error_title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
