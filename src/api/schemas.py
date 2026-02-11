"""Request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────


class TriggerAlertRequest(BaseModel):
    scenario_type: str = Field(
        default="latent_config_bug",
        description="Failure scenario to simulate",
        examples=["latent_config_bug", "memory_leak", "cascading_failure", "traffic_spike"],
    )
    seed: int = Field(default=42, description="Random seed for data generation")
    severity: str = Field(default="critical", examples=["critical", "high", "medium", "low"])


# ── Response Schemas ─────────────────────────────────────────────


class InvestigationCreatedResponse(BaseModel):
    investigation_id: str
    status: str = "detecting"
    message: str = "Investigation started"


class AlertSummary(BaseModel):
    service: str
    metric: str
    value: float
    threshold: float
    severity: str
    description: str


class FindingSummary(BaseModel):
    agent_name: str
    summary: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class InvestigationDetailResponse(BaseModel):
    id: str
    status: str
    scenario_type: Optional[str] = None
    alert: Optional[AlertSummary] = None
    plan: Optional[dict] = None
    findings: list[FindingSummary] = Field(default_factory=list)
    root_cause: Optional[str] = None
    confidence: Optional[float] = None
    recommendation: Optional[str] = None
    remediation_action: Optional[str] = None
    reasoning_trace: list[str] = Field(default_factory=list)
    agent_errors: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


class InvestigationListItem(BaseModel):
    id: str
    status: str
    scenario_type: Optional[str] = None
    alert_service: Optional[str] = None
    alert_description: Optional[str] = None
    confidence: Optional[float] = None
    created_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


class InvestigationListResponse(BaseModel):
    investigations: list[InvestigationListItem]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str = "ok"
    investigation_running: bool = False
    current_investigation_id: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
