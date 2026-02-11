"""Investigation query endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.schemas import (
    AlertSummary,
    FindingSummary,
    InvestigationDetailResponse,
    InvestigationListItem,
    InvestigationListResponse,
)
from src.db.repository import count_investigations, get_investigation, list_investigations

router = APIRouter()


def _record_to_detail(record) -> InvestigationDetailResponse:
    """Convert a DB record to a detail response."""
    alert = None
    if record.alert_data:
        alert = AlertSummary(
            service=record.alert_data.get("service", ""),
            metric=record.alert_data.get("metric", ""),
            value=record.alert_data.get("value", 0),
            threshold=record.alert_data.get("threshold", 0),
            severity=record.alert_data.get("severity", ""),
            description=record.alert_data.get("description", ""),
        )

    findings = []
    if record.findings_data:
        for f in record.findings_data:
            findings.append(
                FindingSummary(
                    agent_name=f.get("agent_name", ""),
                    summary=f.get("summary", ""),
                    confidence=f.get("confidence", 0.0),
                    evidence=f.get("evidence", []),
                )
            )

    return InvestigationDetailResponse(
        id=record.id,
        status=record.status,
        scenario_type=record.scenario_type,
        alert=alert,
        plan=record.plan_data,
        findings=findings,
        root_cause=record.root_cause,
        confidence=record.confidence,
        recommendation=record.recommendation,
        remediation_action=record.remediation_action,
        reasoning_trace=record.reasoning_trace or [],
        agent_errors=record.agent_errors or [],
        created_at=record.created_at,
        completed_at=record.completed_at,
        duration_seconds=record.duration_seconds,
    )


def _record_to_list_item(record) -> InvestigationListItem:
    """Convert a DB record to a list item."""
    alert_service = None
    alert_description = None
    if record.alert_data:
        alert_service = record.alert_data.get("service")
        alert_description = record.alert_data.get("description")

    return InvestigationListItem(
        id=record.id,
        status=record.status,
        scenario_type=record.scenario_type,
        alert_service=alert_service,
        alert_description=alert_description,
        confidence=record.confidence,
        created_at=record.created_at,
        duration_seconds=record.duration_seconds,
    )


@router.get("/investigations", response_model=InvestigationListResponse)
async def list_all_investigations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> InvestigationListResponse:
    records = await list_investigations(session, limit=limit, offset=offset, status=status)
    total = await count_investigations(session, status=status)
    return InvestigationListResponse(
        investigations=[_record_to_list_item(r) for r in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/investigations/{investigation_id}", response_model=InvestigationDetailResponse)
async def get_investigation_detail(
    investigation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> InvestigationDetailResponse:
    record = await get_investigation(session, investigation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return _record_to_detail(record)
