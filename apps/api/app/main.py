import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api.v1.agents import router as agents_api_router
from app.api.v1.auth import router as auth_api_router
from app.api.v1.billing import router as billing_api_router
from app.api.v1.business import router as business_api_router
from app.api.v1.knowledge import router as knowledge_api_router
from app.api.v1.leads import router as leads_api_router
from app.api.v1.whatsapp import router as whatsapp_api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.webhooks.razorpay_webhook import router as razorpay_webhook_router
from app.webhooks.stripe_webhook import router as stripe_webhook_router
from app.webhooks.whatsapp import router as whatsapp_webhook_router

configure_logging(debug=settings.debug, environment=settings.environment)

# Maximum request body size accepted by the API (10 MB). Keeps the webhook
# handler safe from oversized Meta payloads that could exhaust memory.
_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


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
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
