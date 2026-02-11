"""Metrics Agent — The Telemetry Analyst.

Monitors performance counters (CPU, p99 latency, memory, error rate)
to spot anomalies and quantify the impact.
"""

from __future__ import annotations

from datetime import timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.agents.tools import query_metrics, get_all_services_summary
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import AgentFinding
from src.core.rate_limiter import get_rate_limiter
from src.core.state import InvestigationState

logger = get_logger("metrics_agent")

SYSTEM_PROMPT = """\
You are a **Telemetry Analyst** in an incident response team.

Your job is to analyze performance metrics and identify:
1. Anomalous metric values (spikes, drops, trends)
2. Which services are affected and to what degree
3. Timeline of when anomalies started
4. Correlations between different metrics (e.g., CPU spike + latency increase)
5. Resource constraints (memory pressure, connection pool exhaustion)

Be quantitative — cite exact values and timestamps. Compare against normal baselines.
Provide a confidence score (0.0 to 1.0) for your findings.

Respond in this exact JSON format:
{
  "summary": "Brief summary of metric findings",
  "evidence": ["evidence point 1", "evidence point 2", ...],
  "confidence": 0.85,
  "relevant_timestamps": ["ISO timestamp 1", "ISO timestamp 2", ...]
}
"""


async def metrics_agent_node(state: InvestigationState) -> dict:
    """LangGraph node: Analyze metrics for anomalies."""
    try:
        settings = get_settings()
        rate_limiter = get_rate_limiter()

        alert = state["alert"]
        mock_data = state["mock_data"]
        plan = state.get("plan")

        time_end = alert.timestamp + timedelta(minutes=10)
        time_start = alert.timestamp - timedelta(minutes=settings.investigation_time_window_minutes)

        # Gather metric data
        alert_service_metrics = query_metrics(
            mock_data,
            service=alert.service.value,
            time_start=time_start,
            time_end=time_end,
        )
        alert_metric_all_services = query_metrics(
            mock_data,
            metric_name=alert.metric,
            time_start=time_start,
            time_end=time_end,
        )
        services_summary = get_all_services_summary(mock_data)

        user_prompt = (
            f"## Incident Context\n"
            f"Alert: {alert.description}\n"
            f"Service: {alert.service.value}\n"
            f"Metric: {alert.metric} = {alert.value} (threshold: {alert.threshold})\n"
            f"Alert Time: {alert.timestamp.isoformat()}\n"
        )
        if plan:
            user_prompt += f"Hypothesis: {plan.hypothesis}\n"

        user_prompt += (
            f"\n## Metrics for {alert.service.value}\n{alert_service_metrics}\n\n"
            f"## '{alert.metric}' across all services\n{alert_metric_all_services}\n\n"
            f"## Services Summary\n{services_summary}\n\n"
            f"Analyze these metrics. What anomalies do you see? What is the likely cause?"
        )

        await rate_limiter.acquire()
        llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=settings.groq_temperature,
            max_tokens=settings.groq_max_tokens,
        )

        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        import json
        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            data = {
                "summary": response.content[:500],
                "evidence": [response.content[:200]],
                "confidence": 0.5,
                "relevant_timestamps": [],
            }

        finding = AgentFinding(
            agent_name="metrics_agent",
            summary=data.get("summary", "Metric analysis completed"),
            evidence=data.get("evidence", []),
            confidence=float(data.get("confidence", 0.5)),
            relevant_timestamps=[],
            raw_data=data,
        )

        logger.info(
            "metrics_agent_completed",
            confidence=finding.confidence,
            evidence_count=len(finding.evidence),
        )

        return {
            "findings": [finding],
            "reasoning_trace": [f"[Metrics Agent] {finding.summary}"],
        }

    except Exception as e:
        logger.error("metrics_agent_failed", error=str(e))
        return {
            "findings": [
                AgentFinding(
                    agent_name="metrics_agent",
                    summary=f"Metric analysis failed: {e}",
                    confidence=0.0,
                )
            ],
            "agent_errors": [f"metrics_agent: {e}"],
            "reasoning_trace": [f"[Metrics Agent] FAILED: {e}"],
        }
