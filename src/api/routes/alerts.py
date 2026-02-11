"""Alert trigger endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_investigation_runner
from src.api.schemas import (
    ErrorResponse,
    InvestigationCreatedResponse,
    TriggerAlertRequest,
)
from src.core.runner import InvestigationAlreadyRunning, InvestigationRunner
from src.data.mock_generator import MockDataGenerator

router = APIRouter()


@router.post(
    "/alert",
    response_model=InvestigationCreatedResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse}},
)
async def trigger_alert(
    request: TriggerAlertRequest,
    runner: InvestigationRunner = Depends(get_investigation_runner),
) -> InvestigationCreatedResponse:
    """Trigger a new investigation from an alert."""
    # Validate scenario type
    available = MockDataGenerator.available_scenarios()
    if request.scenario_type not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario '{request.scenario_type}'. Available: {available}",
        )

    try:
        investigation_id = await runner.start_investigation(
            scenario_type=request.scenario_type,
            seed=request.seed,
            severity=request.severity,
        )
    except InvestigationAlreadyRunning as e:
        raise HTTPException(status_code=409, detail=str(e))

    return InvestigationCreatedResponse(
        investigation_id=investigation_id,
        status="detecting",
        message=f"Investigation started for scenario '{request.scenario_type}'",
    )
