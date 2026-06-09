import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.v1.agents import router as agents_api_router
from app.api.v1.auth import router as auth_api_router
from app.api.v1.leads import router as leads_api_router
from app.api.v1.whatsapp import router as whatsapp_api_router
from app.core.config import settings
from app.webhooks.whatsapp import router as whatsapp_webhook_router

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)


def create_app() -> FastAPI:
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

    # Webhooks live outside `/api/v1` — Meta calls this URL directly and it has
    # its own auth model (signature verification), not the user JWT/org chain.
    app.include_router(whatsapp_webhook_router)
    app.include_router(auth_api_router, prefix=settings.api_v1_prefix)
    app.include_router(whatsapp_api_router, prefix=settings.api_v1_prefix)
    app.include_router(leads_api_router, prefix=settings.api_v1_prefix)
    app.include_router(agents_api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
