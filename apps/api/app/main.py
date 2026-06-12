import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from redis.asyncio import Redis as AsyncRedis
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sqlalchemy import text

from app.api.v1.agents import router as agents_api_router
from app.api.v1.alerts import router as alerts_api_router
from app.api.v1.analytics import router as analytics_api_router
from app.api.v1.auth import router as auth_api_router
from app.api.v1.billing import router as billing_api_router
from app.api.v1.business import router as business_api_router
from app.api.v1.knowledge import router as knowledge_api_router
from app.api.v1.leads import router as leads_api_router
from app.api.v1.team import invite_router, team_router
from app.api.v1.whatsapp import router as whatsapp_api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine
from app.webhooks.razorpay_webhook import router as razorpay_webhook_router
from app.webhooks.stripe_webhook import router as stripe_webhook_router
from app.webhooks.whatsapp import router as whatsapp_webhook_router

configure_logging(debug=settings.debug, environment=settings.environment)

# Maximum request body size accepted by the API (10 MB). Keeps the webhook
# handler safe from oversized Meta payloads that could exhaust memory.
_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


async def _check_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    try:
        redis = AsyncRedis.from_url(settings.redis_url, socket_connect_timeout=2)
        await redis.ping()
        await redis.aclose()
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: fail fast if the DB is unreachable rather than serving 500s.
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    # Shutdown: drain pooled connections so ECS rolling deploys don't kill
    # in-flight queries mid-transaction.
    await engine.dispose()


def create_app() -> FastAPI:
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            environment=settings.environment,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            send_default_pii=False,
        )

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )
        return response

    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def limit_request_body_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return JSONResponse(
                {"detail": "Request body too large"},
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        return await call_next(request)

    # Webhooks live outside `/api/v1` — payment providers and Meta call these
    # URLs directly with their own signature-based auth, not user JWTs.
    app.include_router(whatsapp_webhook_router)
    app.include_router(stripe_webhook_router)
    app.include_router(razorpay_webhook_router)

    app.include_router(auth_api_router, prefix=settings.api_v1_prefix)
    app.include_router(business_api_router, prefix=settings.api_v1_prefix)
    app.include_router(knowledge_api_router, prefix=settings.api_v1_prefix)
    app.include_router(whatsapp_api_router, prefix=settings.api_v1_prefix)
    app.include_router(leads_api_router, prefix=settings.api_v1_prefix)
    app.include_router(agents_api_router, prefix=settings.api_v1_prefix)
    app.include_router(billing_api_router, prefix=settings.api_v1_prefix)
    app.include_router(analytics_api_router, prefix=settings.api_v1_prefix)
    app.include_router(alerts_api_router, prefix=settings.api_v1_prefix)
    app.include_router(team_router, prefix=settings.api_v1_prefix)
    # invite_router uses /invites prefix (no api_v1_prefix) — public URLs must
    # be short and bookmarkable, matching the `/invite/accept?token=...` frontend route.
    app.include_router(invite_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["system"])
    async def health(
        db_ok: bool = Depends(_check_db),
        redis_ok: bool = Depends(_check_redis),
    ) -> JSONResponse:
        all_ok = db_ok and redis_ok
        return JSONResponse(
            content={
                "status": "ok" if all_ok else "degraded",
                "db": "ok" if db_ok else "error",
                "redis": "ok" if redis_ok else "error",
            },
            status_code=200 if all_ok else 503,
        )

    return app


app = create_app()
