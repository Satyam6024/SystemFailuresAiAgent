"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies import get_investigation_runner
from src.api.schemas import HealthResponse
from src.core.runner import InvestigationRunner

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    runner: InvestigationRunner = Depends(get_investigation_runner),
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        investigation_running=runner.is_running,
        current_investigation_id=runner.current_investigation_id,
    )
