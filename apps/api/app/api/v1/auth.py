from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.core.security import is_allowed_redirect_url
from app.db.session import get_db_session
from app.models.user import User
from app.models.whatsapp import Business
from app.schemas.auth import (
    BusinessSummary,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    SessionResponse,
    SignupRequest,
    UserResponse,
)
from app.services import auth_service
from app.services.auth_service import GoTrueError, GoTrueSession

router = APIRouter(prefix="/auth", tags=["auth"])

# Identity (passwords, sessions, refresh, recovery emails) is delegated
# entirely to Supabase Auth — see app/services/auth_service.py. This router's
# job is to: proxy those operations behind a stable backend contract, persist
# sessions as httpOnly cookies (so the SPA never touches raw tokens), and own
# the one custom step Supabase doesn't know about — turning a brand-new
# signup into the admin of their own business.

_REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_session_cookies(response: Response, gotrue_session: GoTrueSession) -> None:
    response.set_cookie(
        settings.auth_access_token_cookie,
        gotrue_session.access_token,
        max_age=gotrue_session.expires_in,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        domain=settings.auth_cookie_domain,
    )
    response.set_cookie(
        settings.auth_refresh_token_cookie,
        gotrue_session.refresh_token,
        max_age=60 * 60 * 24 * 30,  # refresh tokens long-outlive access tokens (30d, matches Supabase defaults)
        path=_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        domain=settings.auth_cookie_domain,
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.auth_access_token_cookie, path="/", domain=settings.auth_cookie_domain)
    response.delete_cookie(settings.auth_refresh_token_cookie, path=_REFRESH_COOKIE_PATH, domain=settings.auth_cookie_domain)


def _session_response(gotrue_session: GoTrueSession, user: User) -> SessionResponse:
    return SessionResponse(
        access_token=gotrue_session.access_token,
        refresh_token=gotrue_session.refresh_token,
        expires_in=gotrue_session.expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/signup", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    _rl: None = rate_limit(max_requests=5, window_seconds=60),
) -> SessionResponse:
    """Create an account, sign the user in, and bootstrap their business.

    The new user becomes `business_admin` of a freshly created business named
    `business_name` — the only self-serve path to that role (super_admin is
    granted out-of-band; team_member accounts are created via invites).
    """
    try:
        gotrue_session = await auth_service.sign_up(email=payload.email, password=payload.password, full_name=payload.full_name)
    except GoTrueError as exc:
        if exc.status_code == 202:
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Account created — check your email to confirm before signing in",
            ) from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc

    user = await auth_service.bootstrap_business_for_new_user(
        session,
        user_id=gotrue_session.user_id,
        email=payload.email,
        full_name=payload.full_name,
        business_name=payload.business_name,
    )
    await session.commit()

    _set_session_cookies(response, gotrue_session)
    return _session_response(gotrue_session, user)


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    _rl: None = rate_limit(max_requests=10, window_seconds=60),
) -> SessionResponse:
    try:
        gotrue_session = await auth_service.sign_in_with_password(email=payload.email, password=payload.password)
    except GoTrueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password") from exc

    user = await session.get(User, gotrue_session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No account found for this session")

    _set_session_cookies(response, gotrue_session)
    return _session_response(gotrue_session, user)


@router.post("/refresh", response_model=SessionResponse)
async def refresh(
    payload: RefreshRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    refresh_token_cookie: str | None = Cookie(None, alias=settings.auth_refresh_token_cookie),
    _rl: None = rate_limit(max_requests=30, window_seconds=60),
) -> SessionResponse:
    """Exchange a refresh token for a new session.

    Accepts the refresh token from the request body (non-browser clients) or
    the httpOnly cookie (the SPA — `apiFetch` calls this with no body on a
    401 and retries the original request transparently).
    """
    refresh_token = payload.refresh_token or refresh_token_cookie
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    try:
        gotrue_session = await auth_service.refresh_session(refresh_token=refresh_token)
    except GoTrueError as exc:
        _clear_session_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired — please sign in again") from exc

    user = await session.get(User, gotrue_session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No account found for this session")

    _set_session_cookies(response, gotrue_session)
    return _session_response(gotrue_session, user)


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response, current_user: User = Depends(get_current_user)) -> MessageResponse:
    # Token revocation is best-effort server-side; clearing the cookies is
    # what actually ends the session from the browser's perspective.
    _clear_session_cookies(response)
    return MessageResponse(message="Signed out")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    _rl: None = rate_limit(max_requests=3, window_seconds=300),
) -> MessageResponse:
    """Always returns success — never reveal whether an email is registered."""
    if not is_allowed_redirect_url(payload.redirect_to):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="redirect_to must be a registered frontend URL")
    try:
        await auth_service.send_password_recovery_email(email=payload.email, redirect_to=payload.redirect_to)
    except GoTrueError:
        pass
    return MessageResponse(message="If that email is registered, a password reset link is on its way")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    _rl: None = rate_limit(max_requests=5, window_seconds=300),
) -> MessageResponse:
    """Complete a password reset using the recovery session from the emailed link.

    The frontend's reset-password page exchanges the link's recovery token
    for a short-lived session (via Supabase's client SDK) and forwards that
    session's access token here alongside the new password.
    """
    try:
        await auth_service.update_password(recovery_access_token=payload.access_token, new_password=payload.new_password)
    except GoTrueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid or has expired") from exc
    return MessageResponse(message="Password updated — you can now sign in with your new password")


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> MeResponse:
    business = await session.get(Business, current_user.business_id) if current_user.business_id else None
    return MeResponse(
        user=UserResponse.model_validate(current_user),
        business=BusinessSummary.model_validate(business) if business else None,
    )
