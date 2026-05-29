from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.gmail.client import configure_local_oauth_transport

configure_local_oauth_transport(get_settings().google_oauth_redirect_uri)

from app.api.google_oauth import router as google_oauth_router
from app.api.cron import router as cron_router
from app.api.line_webhook import router as line_webhook_router
from app.scheduler.tasks import setup_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.use_apscheduler:
        setup_scheduler()
    yield
    if settings.use_apscheduler:
        shutdown_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.get(f"{settings.api_prefix}/status")
    async def status():
        return {
            "app": settings.app_name,
            "scheduler_enabled": settings.scheduler_enabled,
            "use_apscheduler": settings.use_apscheduler,
            "is_vercel": settings.is_vercel,
            "cron_configured": bool((settings.cron_secret or "").strip()),
        }

    app.include_router(google_oauth_router, prefix=settings.api_prefix)
    app.include_router(line_webhook_router, prefix=settings.api_prefix)
    app.include_router(cron_router, prefix=settings.api_prefix)

    return app


app = create_app()
