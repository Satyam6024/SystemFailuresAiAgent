"""Mock data generation facade."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.core.models import MockDataSet
from src.data.scenarios import SCENARIOS


class MockDataGenerator:
    """Generates correlated mock data for a specified failure scenario."""

    @staticmethod
    def available_scenarios() -> list[str]:
        return list(SCENARIOS.keys())

    @staticmethod
    def generate(
        scenario_type: str,
        seed: int = 42,
        severity: str = "critical",
        incident_time: Optional[datetime] = None,
    ) -> MockDataSet:
        if scenario_type not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario '{scenario_type}'. "
                f"Available: {list(SCENARIOS.keys())}"
            )
        scenario = SCENARIOS[scenario_type]
        return scenario.generate(
            seed=seed,
            severity=severity,
            incident_time=incident_time,
        )
