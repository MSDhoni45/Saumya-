import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Mirrors the `users_role_check` constraint (migration 20260608140002).
UserRole = Literal["super_admin", "business_admin", "team_member"]


# --- Signup / login -----------------------------------------------------------


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    full_name: str = Field(..., min_length=1, max_length=200)
    business_name: str = Field(..., min_length=1, max_length=200, description="Name of the business being created")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)


class RefreshRequest(BaseModel):
    """Optional explicit refresh — the cookie-based session refreshes itself

    via `/auth/refresh` with no body; this lets non-browser clients (mobile,
    CLI, server-to-server) refresh by passing the refresh token directly.
    """

    refresh_token: str | None = None


# --- Password recovery ---------------------------------------------------------


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    redirect_to: str = Field(..., description="Frontend URL the recovery email link should land on")


class ResetPasswordRequest(BaseModel):
    """Submitted from the reset-password page using the recovery session

    Supabase establishes when the user follows the emailed link (the frontend
    exchanges the recovery token for a session, then calls this with that
    session's access token plus the new password).
    """

    access_token: str = Field(..., description="Access token from the Supabase password-recovery session")
    new_password: str = Field(..., min_length=8, max_length=72)


# --- Session / identity ---------------------------------------------------------


class SessionResponse(BaseModel):
    """Returned by every endpoint that establishes or refreshes a session.

    Tokens are also set as httpOnly cookies — they're echoed in the body only
    so non-browser clients (mobile apps, server-to-server integrations) that
    can't rely on cookie jars can store them explicitly.
    """

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: Literal["bearer"] = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID | None
    email: str
    full_name: str | None
    avatar_url: str | None
    role: UserRole
    created_at: datetime


class MeResponse(BaseModel):
    user: UserResponse
    business: "BusinessSummary | None"


class BusinessSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    industry: str | None
    timezone: str
    onboarding_completed: bool


class MessageResponse(BaseModel):
    message: str
