"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.logging import configure_logging, get_logger
from src.db.engine import dispose_engine, get_engine
from src.db.models import Base

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create tables on startup, dispose engine on shutdown."""
    configure_logging()
    logger.info("api_starting")

    # Create tables (in production, use Alembic migrations instead)
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_ready")

    yield

    await dispose_engine()
    logger.info("api_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="System Failures AI Agent",
        description="Autonomous AI First Responder for diagnosing complex system failures",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Register routes
    from src.api.routes import alerts, health, investigations, metrics, reports

    app.include_router(health.router, tags=["health"])
    app.include_router(metrics.router, tags=["metrics"])
    app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
    app.include_router(investigations.router, prefix="/api/v1", tags=["investigations"])
    app.include_router(reports.router, prefix="/api/v1", tags=["reports"])

    return app
