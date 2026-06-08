import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.whatsapp import Business

_TZ_DATETIME = DateTime(timezone=True)

# Mirrors the `users_role_check` constraint added in migration
# 20260608140002_auth_rbac_roles.sql.
UserRole = Literal["super_admin", "business_admin", "team_member"]


class User(Base):
    """Product-level profile for a Supabase `auth.users` row.

    1:1 with `auth.users` (same primary key — provisioned by the
    `handle_new_auth_user` trigger on signup). `business_id` is nullable so
    `super_admin` accounts (platform operators, granted out-of-band — never
    via self-serve signup) aren't bound to a single tenant.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="SET NULL")
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(String, nullable=False, default="business_admin")
    created_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ_DATETIME, server_default=func.now())

    business: Mapped["Business | None"] = relationship(back_populates="users")
