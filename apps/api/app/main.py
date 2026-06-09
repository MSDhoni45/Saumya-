import logging

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api.v1.agents import router as agents_api_router
from app.api.v1.auth import router as auth_api_router
from app.api.v1.business import router as business_api_router
from app.api.v1.knowledge import router as knowledge_api_router
from app.api.v1.leads import router as leads_api_router
from app.api.v1.whatsapp import router as whatsapp_api_router
from app.core.config import settings
from app.webhooks.whatsapp import router as whatsapp_webhook_router

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)

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

    # Webhooks live outside `/api/v1` — Meta calls this URL directly and it has
    # its own auth model (signature verification), not the user JWT/org chain.
    app.include_router(whatsapp_webhook_router)
    app.include_router(auth_api_router, prefix=settings.api_v1_prefix)
    app.include_router(business_api_router, prefix=settings.api_v1_prefix)
    app.include_router(knowledge_api_router, prefix=settings.api_v1_prefix)
    app.include_router(whatsapp_api_router, prefix=settings.api_v1_prefix)
    app.include_router(leads_api_router, prefix=settings.api_v1_prefix)
    app.include_router(agents_api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
