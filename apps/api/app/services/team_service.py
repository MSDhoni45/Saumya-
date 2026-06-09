from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import TeamInvite
from app.models.user import User
from app.models.whatsapp import Business

logger = logging.getLogger(__name__)

_INVITE_TTL_DAYS = 7


class TeamError(Exception):
    """Raised for expected business-rule violations (maps to 4xx responses)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.status_code = status_code
        super().__init__(message)


async def list_members(session: AsyncSession, business_id: uuid.UUID) -> list[User]:
    stmt = (
        select(User)
        .where(User.business_id == business_id)
        .order_by(User.role.asc(), User.created_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def remove_member(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Detach a user from the business. Does NOT delete their auth account."""
    if user_id == actor_id:
        raise TeamError("You cannot remove yourself from the team.")

    user = await session.get(User, user_id)
    if user is None or user.business_id != business_id:
        raise TeamError("Team member not found.", status_code=404)

    if user.role == "business_admin":
        admin_count = await _count_admins(session, business_id)
        if admin_count <= 1:
            raise TeamError("Cannot remove the last business admin. Assign another admin first.")

    user.business_id = None
    user.role = "team_member"


async def change_role(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    new_role: str,
    actor_id: uuid.UUID,
) -> User:
    if user_id == actor_id:
        raise TeamError("You cannot change your own role.")

    user = await session.get(User, user_id)
    if user is None or user.business_id != business_id:
        raise TeamError("Team member not found.", status_code=404)

    if user.role == new_role:
        return user

    if user.role == "business_admin" and new_role == "team_member":
        admin_count = await _count_admins(session, business_id)
        if admin_count <= 1:
            raise TeamError("Cannot demote the last business admin. Assign another admin first.")

    user.role = new_role  # type: ignore[assignment]
    return user


async def create_invite(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    email: str,
    role: str,
    invited_by_id: uuid.UUID,
) -> TeamInvite:
    email_lower = email.lower()

    # Already a member?
    existing_user = await session.scalar(
        select(User).where(
            func.lower(User.email) == email_lower,
            User.business_id == business_id,
        )
    )
    if existing_user is not None:
        raise TeamError(f"{email} is already a member of this team.")

    # Pending invite already exists?
    existing_invite = await session.scalar(
        select(TeamInvite).where(
            func.lower(TeamInvite.email) == email_lower,
            TeamInvite.business_id == business_id,
            TeamInvite.status == "pending",
            TeamInvite.expires_at > datetime.now(tz=timezone.utc),
        )
    )
    if existing_invite is not None:
        raise TeamError(f"A pending invite for {email} already exists.")

    invite = TeamInvite(
        business_id=business_id,
        invited_by_id=invited_by_id,
        email=email_lower,
        role=role,
        token=secrets.token_urlsafe(32),
        status="pending",
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=_INVITE_TTL_DAYS),
    )
    session.add(invite)
    await session.flush()
    return invite


async def list_invites(session: AsyncSession, business_id: uuid.UUID) -> list[TeamInvite]:
    stmt = (
        select(TeamInvite)
        .where(
            TeamInvite.business_id == business_id,
            TeamInvite.status == "pending",
            TeamInvite.expires_at > datetime.now(tz=timezone.utc),
        )
        .order_by(TeamInvite.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def revoke_invite(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    invite_id: uuid.UUID,
) -> None:
    invite = await session.get(TeamInvite, invite_id)
    if invite is None or invite.business_id != business_id:
        raise TeamError("Invite not found.", status_code=404)
    if invite.status != "pending":
        raise TeamError("Only pending invites can be revoked.")
    invite.status = "revoked"


async def get_invite_by_token(session: AsyncSession, token: str) -> TeamInvite | None:
    return await session.scalar(select(TeamInvite).where(TeamInvite.token == token))


async def accept_invite(
    session: AsyncSession,
    *,
    invite: TeamInvite,
    user: User,
) -> User:
    """Link `user` to the business from the invite and mark it accepted."""
    if user.business_id is not None and user.business_id != invite.business_id:
        raise TeamError(
            "You already belong to another workspace. "
            "Contact your current admin to remove you before accepting a new invite.",
            status_code=409,
        )

    user.business_id = invite.business_id
    user.role = invite.role  # type: ignore[assignment]
    invite.status = "accepted"
    invite.accepted_by_id = user.id
    return user


async def get_invite_context(
    session: AsyncSession,
    invite: TeamInvite,
) -> tuple[str, str | None]:
    """Return (business_name, invited_by_full_name) for display on the accept page."""
    business = await session.get(Business, invite.business_id)
    business_name = business.name if business else "Unknown Business"

    invited_by_name: str | None = None
    if invite.invited_by_id:
        inviter = await session.get(User, invite.invited_by_id)
        if inviter:
            invited_by_name = inviter.full_name or inviter.email

    return business_name, invited_by_name


async def _count_admins(session: AsyncSession, business_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count()).where(
            User.business_id == business_id,
            User.role == "business_admin",
        )
    )
    return result.scalar_one()
