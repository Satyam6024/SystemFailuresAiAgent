"""System Failures AI Agent — Main entry point.

Runs a full investigation against a simulated failure scenario.
"""

from __future__ import annotations

import asyncio
import sys
import time

from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger
from src.core.models import InvestigationStatus
from src.data.mock_generator import MockDataGenerator
from src.graph.investigation import build_investigation_graph


async def run_investigation(scenario: str = "latent_config_bug", seed: int = 42) -> None:
    """Run a complete investigation for the given scenario."""
    configure_logging()
    logger = get_logger("main")
    settings = get_settings()

    if not settings.groq_api_key:
        logger.error("missing_api_key", msg="Set SFA_GROQ_API_KEY in .env file")
        sys.exit(1)

    logger.info(
        "starting_investigation",
        scenario=scenario,
        model=settings.groq_model,
    )

    # Generate mock data for the scenario
    logger.info("generating_mock_data", scenario=scenario, seed=seed)
    mock_data = MockDataGenerator.generate(scenario, seed=seed)
    logger.info(
        "mock_data_ready",
        logs=len(mock_data.logs),
        metrics=len(mock_data.metrics),
        deployments=len(mock_data.deployments),
    )

    # Build the LangGraph investigation graph
    graph = build_investigation_graph()

    # Initial state
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

    # Run the investigation
    start_time = time.monotonic()
    logger.info("graph_executing")

    result = await graph.ainvoke(initial_state)

    elapsed = time.monotonic() - start_time
    logger.info("investigation_complete", duration_seconds=f"{elapsed:.1f}")

    # Print the report
    report = result.get("report")
    if report:
        print("\n" + "=" * 70)
        print("  ROOT CAUSE ANALYSIS REPORT")
        print("=" * 70)
        print(f"\n  Investigation ID: {report.investigation_id}")
        print(f"  Status: {report.status.value}")
        print(f"  Duration: {elapsed:.1f}s")
        print(f"\n  Alert: {report.alert.description}")
        print(f"  Service: {report.alert.service.value}")
        print(f"  Severity: {report.alert.severity.value}")
        print(f"\n  Root Cause: {report.root_cause}")
        print(f"  Confidence: {report.confidence:.0%}")
        print(f"\n  Recommendation: {report.recommendation}")
        if report.remediation_action:
            print(f"  Remediation: {report.remediation_action}")

        print(f"\n  Findings ({len(report.findings)} agents):")
        for f in report.findings:
            print(f"    [{f.agent_name}] (confidence: {f.confidence:.0%})")
            print(f"      {f.summary[:200]}")

        print(f"\n  Reasoning Trace:")
        for i, trace in enumerate(result.get("reasoning_trace", []), 1):
            print(f"    {i}. {trace[:150]}")

        print("\n" + "=" * 70)

        # Also dump full JSON report
        print("\n--- Full JSON Report ---")
        print(report.model_dump_json(indent=2))
    else:
        logger.error("no_report_generated")
        print("\nERROR: No report was generated.")


def main() -> None:
    """CLI entry point."""
    scenario = sys.argv[1] if len(sys.argv) > 1 else "latent_config_bug"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42

    available = MockDataGenerator.available_scenarios()
    if scenario not in available:
        print(f"Unknown scenario: {scenario}")
        print(f"Available: {available}")
        sys.exit(1)

    asyncio.run(run_investigation(scenario=scenario, seed=seed))


if __name__ == "__main__":
    main()
