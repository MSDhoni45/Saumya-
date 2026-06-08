import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.user import User
from app.models.whatsapp import Business

# All identity operations (credential checks, hashing, session minting/rotation,
# recovery emails) are delegated to Supabase Auth's GoTrue REST API — this
# service is a thin, typed wrapper over it. The backend never sees or stores a
# raw password.


class GoTrueError(Exception):
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"Supabase Auth error ({status_code}): {payload}")

    @property
    def message(self) -> str:
        if isinstance(self.payload, dict):
            return str(self.payload.get("error_description") or self.payload.get("msg") or self.payload)
        return str(self.payload)


@dataclass(frozen=True, slots=True)
class GoTrueSession:
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: uuid.UUID
    email: str | None


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, GoTrueError) and exc.status_code >= 500


def _headers(*, bearer: str | None = None) -> dict[str, str]:
    headers = {"apikey": settings.supabase_anon_key, "Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


def _session_from_payload(payload: dict[str, Any]) -> GoTrueSession:
    user = payload.get("user") or {}
    return GoTrueSession(
        access_token=payload["access_token"],
        refresh_token=payload["refresh_token"],
        expires_in=payload["expires_in"],
        user_id=uuid.UUID(user["id"]),
        email=user.get("email"),
    )


@retry(
    retry=retry_if_exception(_retryable),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def _request(method: str, path: str, *, bearer: str | None = None, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(base_url=settings.supabase_auth_url, timeout=15.0) as client:
        response = await client.request(method, path, headers=_headers(bearer=bearer), **kwargs)
    if response.status_code >= 400:
        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text
        raise GoTrueError(response.status_code, payload)
    return response


# --- Signup / login / refresh / logout ----------------------------------------


async def sign_up(*, email: str, password: str, full_name: str) -> GoTrueSession:
    """Create a Supabase Auth user. The `handle_new_auth_user` DB trigger

    (migration 20260608130002) provisions the matching `users` row; the
    caller is responsible for the one custom step Supabase doesn't know about
    — turning that user into the admin of a brand-new business (see
    `bootstrap_business_for_new_user`).
    """
    response = await _request(
        "POST",
        "/signup",
        json={"email": email, "password": password, "data": {"full_name": full_name}},
    )
    payload = response.json()
    if "access_token" not in payload:
        # Email-confirmation is enabled on the project — there's no session
        # yet, only a pending user. Surface this distinctly so the router can
        # return a "check your email" response instead of a session.
        raise GoTrueError(202, {"error_description": "Email confirmation required before a session is issued"})
    return _session_from_payload(payload)


async def sign_in_with_password(*, email: str, password: str) -> GoTrueSession:
    response = await _request("POST", "/token", params={"grant_type": "password"}, json={"email": email, "password": password})
    return _session_from_payload(response.json())


async def refresh_session(*, refresh_token: str) -> GoTrueSession:
    response = await _request("POST", "/token", params={"grant_type": "refresh_token"}, json={"refresh_token": refresh_token})
    return _session_from_payload(response.json())


async def sign_out(*, access_token: str) -> None:
    # Best-effort: revokes the refresh token family server-side. A failure
    # here must never block the user from being logged out locally — the
    # caller clears cookies regardless.
    try:
        await _request("POST", "/logout", bearer=access_token, params={"scope": "local"})
    except GoTrueError:
        pass


# --- Password recovery ----------------------------------------------------------


async def send_password_recovery_email(*, email: str, redirect_to: str) -> None:
    await _request("POST", "/recover", params={"redirect_to": redirect_to}, json={"email": email})


async def update_password(*, recovery_access_token: str, new_password: str) -> None:
    await _request("PUT", "/user", bearer=recovery_access_token, json={"password": new_password})


# --- Signup completion: bootstrap a business for a brand-new user ---------------


async def bootstrap_business_for_new_user(
    session: AsyncSession, *, user_id: uuid.UUID, email: str, full_name: str, business_name: str
) -> User:
    """Idempotently turn a freshly-signed-up user into a business admin.

    Mirrors the `/auth/bootstrap` step described in the architecture docs,
    adapted to the businesses/users schema: create the business, then attach
    the user (already provisioned by the `handle_new_auth_user` trigger) to
    it as `business_admin`. Safe to call more than once — e.g. if the
    frontend retries after a network blip — it returns the existing
    membership rather than creating a duplicate business.
    """
    user = await session.get(User, user_id)
    if user is None:
        # Trigger hasn't committed yet (replication lag) — provision directly
        # so the bootstrap never fails on a race with Supabase's webhook path.
        user = User(id=user_id, email=email, full_name=full_name, role="business_admin")
        session.add(user)
        await session.flush()

    if user.business_id is not None:
        return user

    business = Business(name=business_name)
    session.add(business)
    await session.flush()

    user.business_id = business.id
    user.role = "business_admin"
    if not user.full_name:
        user.full_name = full_name
    await session.flush()
    await session.refresh(user)
    return user
