"""Data access layer for investigation records."""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import InvestigationRecord


async def create_investigation(
    session: AsyncSession,
    *,
    investigation_id: str,
    alert_data: dict,
    scenario_type: str | None = None,
) -> InvestigationRecord:
    record = InvestigationRecord(
        id=investigation_id,
        alert_data=alert_data,
        status="detecting",
        scenario_type=scenario_type,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def update_investigation(
    session: AsyncSession,
    investigation_id: str,
    **kwargs,
) -> InvestigationRecord | None:
    record = await session.get(InvestigationRecord, investigation_id)
    if record is None:
        return None
    for key, value in kwargs.items():
        if hasattr(record, key):
            setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return record


async def get_investigation(
    session: AsyncSession,
    investigation_id: str,
) -> InvestigationRecord | None:
    return await session.get(InvestigationRecord, investigation_id)


async def list_investigations(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
) -> list[InvestigationRecord]:
    stmt = select(InvestigationRecord).order_by(desc(InvestigationRecord.created_at))
    if status:
        stmt = stmt.where(InvestigationRecord.status == status)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_investigations(
    session: AsyncSession,
    *,
    status: Optional[str] = None,
) -> int:
    from sqlalchemy import func as sa_func
    stmt = select(sa_func.count(InvestigationRecord.id))
    if status:
        stmt = stmt.where(InvestigationRecord.status == status)
    result = await session.execute(stmt)
    return result.scalar_one()
