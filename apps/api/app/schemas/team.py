from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    role: str
    created_at: datetime


class InviteRequest(BaseModel):
    email: EmailStr
    role: Literal["business_admin", "team_member"] = "team_member"


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    invited_by_name: str | None = None
    created_at: datetime


class ChangeRoleRequest(BaseModel):
    role: Literal["business_admin", "team_member"]


class InviteDetailsResponse(BaseModel):
    """Public information shown on the accept-invite page (no auth required)."""

    id: uuid.UUID
    email: str
    role: str
    business_name: str
    invited_by_name: str | None
    is_valid: bool
    expired: bool


class AcceptInviteRequest(BaseModel):
    """For new users creating an account inline.

    Omit both fields (or send an empty body) when the caller is already
    authenticated — the invite will be linked to their existing account.
    """

    full_name: str | None = Field(None, min_length=1, max_length=200)
    password: str | None = Field(None, min_length=8, max_length=72)


class AcceptInviteResponse(BaseModel):
    message: str
    business_name: str
    role: str
