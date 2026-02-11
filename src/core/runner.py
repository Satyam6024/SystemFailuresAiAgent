"""InvestigationRunner — orchestrates a single investigation lifecycle.

Enforces one-at-a-time execution via asyncio.Lock and persists state
to the database after each graph node completes.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Optional
from uuid import uuid4

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import InvestigationStatus, MockDataSet
from src.data.mock_generator import MockDataGenerator
from src.db.engine import get_session_factory
from src.db.repository import create_investigation, update_investigation
from src.graph.investigation import build_investigation_graph

logger = get_logger("runner")


class InvestigationAlreadyRunning(Exception):
    pass


class InvestigationRunner:
    """Manages investigation execution with one-at-a-time constraint."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._current_id: Optional[str] = None
        self._graph = build_investigation_graph()

    @property
    def is_running(self) -> bool:
        return self._lock.locked()

    @property
    def current_investigation_id(self) -> Optional[str]:
        return self._current_id

    async def start_investigation(
        self,
        *,
        scenario_type: str = "latent_config_bug",
        seed: int = 42,
        severity: str = "critical",
    ) -> str:
        """Start a new investigation. Returns the investigation ID.

        Raises InvestigationAlreadyRunning if one is in progress.
        """
        if self._lock.locked():
            raise InvestigationAlreadyRunning(
                f"Investigation {self._current_id} is already in progress"
            )

        investigation_id = uuid4().hex[:16]

        # Generate mock data
        mock_data = MockDataGenerator.generate(
            scenario_type, seed=seed, severity=severity
        )

        # Create DB record
        session_factory = get_session_factory()
        async with session_factory() as session:
            await create_investigation(
                session,
                investigation_id=investigation_id,
                alert_data=mock_data.alert.model_dump(mode="json"),
                scenario_type=scenario_type,
            )

        # Launch the investigation in background
        asyncio.create_task(
            self._run(investigation_id, mock_data)
        )

        return investigation_id

    async def _run(self, investigation_id: str, mock_data: MockDataSet) -> None:
        """Execute the investigation graph and persist results."""
        async with self._lock:
            self._current_id = investigation_id
            start_time = time.monotonic()
            session_factory = get_session_factory()

            try:
                logger.info("investigation_started", investigation_id=investigation_id)

                # Update status
                async with session_factory() as session:
                    await update_investigation(
                        session, investigation_id, status="investigating"
                    )

                initial_state = {
                    "alert": mock_data.alert,
                    "mock_data": mock_data,
                    "status": InvestigationStatus.DETECTING,
                    "plan": None,
                    "root_cause": None,
                    "recommendation": None,
                    "confidence": 0.0,
                    "findings": [],
                    "agent_errors": [],
                    "reasoning_trace": [],
                    "report": None,
                    "remediation_action": None,
                    "iteration": 0,
                }

                result = await self._graph.ainvoke(initial_state)

                elapsed = time.monotonic() - start_time
                report = result.get("report")

                # Persist final results
                async with session_factory() as session:
                    update_kwargs = {
                        "status": "completed",
                        "duration_seconds": elapsed,
                        "completed_at": datetime.utcnow(),
                        "reasoning_trace": result.get("reasoning_trace", []),
                        "agent_errors": result.get("agent_errors", []),
                        "confidence": result.get("confidence", 0.0),
                        "root_cause": result.get("root_cause"),
                        "recommendation": result.get("recommendation"),
                        "remediation_action": result.get("remediation_action"),
                    }

                    if result.get("plan"):
                        update_kwargs["plan_data"] = result["plan"].model_dump(mode="json")

                    if result.get("findings"):
                        update_kwargs["findings_data"] = [
                            f.model_dump(mode="json") for f in result["findings"]
                        ]

                    if report:
                        update_kwargs["report_data"] = report.model_dump(mode="json")

                    await update_investigation(session, investigation_id, **update_kwargs)

                logger.info(
                    "investigation_completed",
                    investigation_id=investigation_id,
                    duration=f"{elapsed:.1f}s",
                    confidence=result.get("confidence", 0.0),
                )

            except Exception as e:
                elapsed = time.monotonic() - start_time
                logger.error(
                    "investigation_failed",
                    investigation_id=investigation_id,
                    error=str(e),
                )
                async with session_factory() as session:
                    await update_investigation(
                        session,
                        investigation_id,
                        status="failed",
                        duration_seconds=elapsed,
                        completed_at=datetime.utcnow(),
                        agent_errors=[str(e)],
                    )
            finally:
                self._current_id = None


# Module-level singleton
_runner: InvestigationRunner | None = None


def get_runner() -> InvestigationRunner:
    global _runner
    if _runner is None:
        _runner = InvestigationRunner()
    return _runner
