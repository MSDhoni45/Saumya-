from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

_TZ = DateTime(timezone=True)


class TeamInvite(Base):
    """Pending invitation for a person to join a business as a specific role.

    `token` is the URL-safe opaque value embedded in the invite link — it's
    the only way to look up an invite without being authenticated.
    `invited_by_id` and `accepted_by_id` use ON DELETE SET NULL so the invite
    audit trail survives if those users are later removed from the team.
    """

    __tablename__ = "team_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="team_member")
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # pending | accepted | revoked
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(_TZ, nullable=False)
    accepted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(_TZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ, nullable=False, server_default=func.now(), onupdate=func.now())
