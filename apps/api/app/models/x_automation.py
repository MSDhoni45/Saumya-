import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

_TZ_DATETIME = DateTime(timezone=True)


class XAccount(Base):
    """OAuth 2.0 user tokens for a connected X (Twitter) account."""

    __tablename__ = "x_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    x_user_id: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)   # Fernet-encrypted
    refresh_token: Mapped[str | None] = mapped_column(Text)           # Fernet-encrypted
    token_expires_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    posts: Mapped[list["XPost"]] = relationship(back_populates="x_account", cascade="all, delete-orphan")
    outreach_items: Mapped[list["XOutreach"]] = relationship(back_populates="x_account")


class XPost(Base):
    """A tweet or thread — either a draft, scheduled, or already posted."""

    __tablename__ = "x_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    x_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("x_accounts.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tweet_ids: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    thread_tweets: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    posted_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    error_message: Mapped[str | None] = mapped_column(Text)
    engagement: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    x_account: Mapped["XAccount"] = relationship(back_populates="posts")


class XLeadSearch(Base):
    """Keyword configuration that drives automated lead discovery on X."""

    __tablename__ = "x_lead_searches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    exclude_keywords: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    min_followers: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    outreach_items: Mapped[list["XOutreach"]] = relationship(back_populates="search")


class XOutreach(Base):
    """A discovered X user that has been scored and had outreach drafted for them."""

    __tablename__ = "x_outreach"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL")
    )
    x_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("x_accounts.id", ondelete="SET NULL")
    )
    search_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("x_lead_searches.id", ondelete="SET NULL")
    )
    x_user_id: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String)
    profile_bio: Mapped[str | None] = mapped_column(Text)
    followers_count: Mapped[int | None] = mapped_column(Integer)
    following_count: Mapped[int | None] = mapped_column(Integer)
    tweet_text: Mapped[str | None] = mapped_column(Text)
    tweet_id: Mapped[str | None] = mapped_column(String)
    ai_score: Mapped[int | None] = mapped_column(Integer)
    ai_score_reason: Mapped[str | None] = mapped_column(Text)
    outreach_message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(_TZ_DATETIME)
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    x_account: Mapped["XAccount | None"] = relationship(back_populates="outreach_items")
    search: Mapped["XLeadSearch | None"] = relationship(back_populates="outreach_items")
