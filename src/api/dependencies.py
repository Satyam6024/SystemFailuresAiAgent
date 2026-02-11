"""FastAPI dependency injection."""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.runner import InvestigationRunner, get_runner
from src.db.engine import get_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


def get_investigation_runner() -> InvestigationRunner:
    return get_runner()
