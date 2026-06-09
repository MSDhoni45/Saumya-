import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TokenError, decode_access_token
from app.db.session import get_db_session
from app.models.user import User, UserRole

# Auth surface area for every protected route: resolve the bearer token →
# the `users` row → (optionally) the active business and role. Two layers of
# defense — these dependencies (primary, descriptive 4xxs) and Postgres RLS
# (`auth_business_id`/`auth_is_business_admin`/`auth_is_super_admin`,
# defense-in-depth — see migrations 20260608130008 and 20260608140002).


def _bearer_token(
    authorization: str | None = Header(None),
    cookie_token: str | None = Cookie(None, alias=settings.auth_access_token_cookie),
) -> str:
    """Accept the access token from either an `Authorization: Bearer` header

    (API clients, mobile apps) or the httpOnly session cookie the backend
    issues to the Next.js frontend — whichever is present.
    """
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[len("bearer ") :].strip()
    if cookie_token:
        return cookie_token
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")


async def get_current_user(
    token: str = Depends(_bearer_token),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Validate the access token and load the matching `users` row.

    A valid Supabase JWT with no corresponding `users` row (replication lag
    right after signup, or a JWT for a deleted account) is treated as
    unauthenticated — there's no product identity to act as.
    """
    try:
        claims = decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = await session.get(User, claims.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No account found for this session")
    return user


@dataclass(frozen=True, slots=True)
class BusinessContext:
    user_id: uuid.UUID
    business_id: uuid.UUID
    role: UserRole


async def get_current_business(current_user: User = Depends(get_current_user)) -> BusinessContext:
    """Resolve the business the current request operates on.

    `super_admin` accounts are platform-wide and have no single business —
    routes that need cross-business access should depend on `require_roles
    ("super_admin")` directly rather than this dependency. Everyone else must
    belong to exactly one business (the schema's single-membership model).
    """
    if current_user.role == "super_admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin accounts are not bound to a single business — use a business-scoped admin route",
        )
    if current_user.business_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not attached to a business yet",
        )
    return BusinessContext(user_id=current_user.id, business_id=current_user.business_id, role=current_user.role)


def require_business_access(ctx: BusinessContext, business_id: uuid.UUID) -> None:
    """Raise 403 if the authenticated user's business doesn't match the path parameter."""
    if ctx.business_id != business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Dependency factory enforcing RBAC on a route.

    Usage: `current_user: User = Depends(require_roles("business_admin", "super_admin"))`.
    `super_admin` is implicitly allowed everywhere `business_admin` is, since
    platform operators must be able to act on any tenant's behalf for support
    and moderation — but routes can still require `super_admin` explicitly
    when an action must never be delegated to a tenant admin.
    """
    allowed = set(roles)
    if "business_admin" in allowed:
        allowed.add("super_admin")

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(sorted(allowed))}",
            )
        return current_user

    return _check
