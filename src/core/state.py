"""LangGraph investigation state definition.

The central state flows through every node in the graph.  List fields use
``operator.add`` as a reducer so that parallel agent nodes can all *append*
their findings without overwriting each other.
"""

from __future__ import annotations

import operator
from typing import Annotated, Optional

from typing_extensions import TypedDict

from src.core.models import (
    AgentFinding,
    Alert,
    InvestigationPlan,
    InvestigationStatus,
    MockDataSet,
    RCAReport,
)


class InvestigationState(TypedDict):
    # ── Input ───────────────────────────────────────────────────
    alert: Alert
    mock_data: MockDataSet

    # ── Status ──────────────────────────────────────────────────
    status: InvestigationStatus

    # ── Commander outputs ───────────────────────────────────────
    plan: Optional[InvestigationPlan]
    root_cause: Optional[str]
    recommendation: Optional[str]
    confidence: float

    # ── Agent findings (parallel-safe via reducer) ──────────────
    findings: Annotated[list[AgentFinding], operator.add]
    agent_errors: Annotated[list[str], operator.add]

    # ── Reasoning trace (append-only log of decisions) ──────────
    reasoning_trace: Annotated[list[str], operator.add]

    # ── Final report ────────────────────────────────────────────
    report: Optional[RCAReport]

    # ── Remediation action taken ────────────────────────────────
    remediation_action: Optional[str]

    # ── Metadata ────────────────────────────────────────────────
    iteration: int
