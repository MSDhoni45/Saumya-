from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BusinessContext, get_current_business, get_optional_current_user, require_business_access
from app.core.config import settings
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.team import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    ChangeRoleRequest,
    InviteDetailsResponse,
    InviteRequest,
    InviteResponse,
    TeamMemberResponse,
)
from app.services import email_service, team_service
from app.services.team_service import TeamError

logger = logging.getLogger(__name__)

team_router = APIRouter(prefix="/team", tags=["team"])
invite_router = APIRouter(prefix="/invites", tags=["invites"])


def _raise_team_error(exc: TeamError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _require_admin(ctx: BusinessContext) -> None:
    if ctx.role not in ("business_admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Business admin required")


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@team_router.get("/{business_id}/members", response_model=list[TeamMemberResponse])
async def list_members(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[TeamMemberResponse]:
    require_business_access(ctx, business_id)
    members = await team_service.list_members(session, business_id)
    return [TeamMemberResponse.model_validate(m) for m in members]


@team_router.delete("/{business_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_member(
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    require_business_access(ctx, business_id)
    _require_admin(ctx)
    try:
        await team_service.remove_member(
            session,
            business_id=business_id,
            user_id=user_id,
            actor_id=ctx.user_id,
        )
    except TeamError as exc:
        _raise_team_error(exc)
    await session.commit()


@team_router.patch("/{business_id}/members/{user_id}", response_model=TeamMemberResponse)
async def change_member_role(
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ChangeRoleRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> TeamMemberResponse:
    require_business_access(ctx, business_id)
    _require_admin(ctx)
    try:
        user = await team_service.change_role(
            session,
            business_id=business_id,
            user_id=user_id,
            new_role=body.role,
            actor_id=ctx.user_id,
        )
    except TeamError as exc:
        _raise_team_error(exc)
    await session.commit()
    return TeamMemberResponse.model_validate(user)


# ---------------------------------------------------------------------------
# Invites (admin-facing)
# ---------------------------------------------------------------------------


@team_router.post(
    "/{business_id}/invites",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    business_id: uuid.UUID,
    body: InviteRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> InviteResponse:
    require_business_access(ctx, business_id)
    _require_admin(ctx)
    try:
        invite = await team_service.create_invite(
            session,
            business_id=business_id,
            email=str(body.email),
            role=body.role,
            invited_by_id=ctx.user_id,
        )
    except TeamError as exc:
        _raise_team_error(exc)
    await session.commit()
    await session.refresh(invite)

    try:
        business_name, inviter_name = await team_service.get_invite_context(session, invite)
        base_url = settings.app_frontend_url or (
            settings.allowed_origins[0] if settings.allowed_origins else "http://localhost:3000"
        )
        accept_url = f"{base_url}/invite/accept?token={invite.token}"
        await email_service.send_invite_email(
            to_email=invite.email,
            business_name=business_name,
            invited_by_name=inviter_name or "A team admin",
            role=invite.role,
            accept_url=accept_url,
        )
    except Exception:
        logger.exception("Failed to send invite email for invite_id=%s", invite.id)

    return InviteResponse.model_validate(invite)


@team_router.get("/{business_id}/invites", response_model=list[InviteResponse])
async def list_invites(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[InviteResponse]:
    require_business_access(ctx, business_id)
    _require_admin(ctx)
    invites = await team_service.list_invites(session, business_id)
    return [InviteResponse.model_validate(i) for i in invites]


@team_router.delete("/{business_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def revoke_invite(
    business_id: uuid.UUID,
    invite_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    require_business_access(ctx, business_id)
    _require_admin(ctx)
    try:
        await team_service.revoke_invite(session, business_id=business_id, invite_id=invite_id)
    except TeamError as exc:
        _raise_team_error(exc)
    await session.commit()


# ---------------------------------------------------------------------------
# Public invite endpoints (no auth required to view; optional auth to accept)
# ---------------------------------------------------------------------------


@invite_router.get("/{token}", response_model=InviteDetailsResponse)
async def get_invite_details(
    token: str,
    session: AsyncSession = Depends(get_db_session),
) -> InviteDetailsResponse:
    invite = await team_service.get_invite_by_token(session, token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    now = datetime.now(tz=timezone.utc)
    expired = invite.expires_at < now
    is_valid = invite.status == "pending" and not expired
    business_name, invited_by_name = await team_service.get_invite_context(session, invite)

    return InviteDetailsResponse(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        business_name=business_name,
        invited_by_name=invited_by_name,
        is_valid=is_valid,
        expired=expired,
    )


@invite_router.post("/{token}/accept", response_model=AcceptInviteResponse)
async def accept_invite(
    token: str,
    body: AcceptInviteRequest,
    current_user: User | None = Depends(get_optional_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AcceptInviteResponse:
    invite = await team_service.get_invite_by_token(session, token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    now = datetime.now(tz=timezone.utc)
    if invite.status != "pending" or invite.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invite has expired or has already been used",
        )

    if current_user is None:
        if not body.full_name or not body.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="full_name and password are required to create a new account",
            )
        from app.services.auth_service import GoTrueError, sign_up

        try:
            gts = await sign_up(
                email=invite.email,
                password=body.password,
                full_name=body.full_name,
            )
        except GoTrueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

        current_user = await session.get(User, gts.user_id)
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Account created but profile not ready — please sign in to accept",
            )

    business_name, _ = await team_service.get_invite_context(session, invite)
    try:
        await team_service.accept_invite(session, invite=invite, user=current_user)
    except TeamError as exc:
        _raise_team_error(exc)
    await session.commit()

    role_label = invite.role.replace("_", " ").title()
    return AcceptInviteResponse(
        message=f"You've joined {business_name} as {role_label}.",
        business_name=business_name,
        role=invite.role,
    )
