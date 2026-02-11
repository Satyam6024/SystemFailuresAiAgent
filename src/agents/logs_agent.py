"""Logs Agent — The Forensic Expert.

Deep-scans distributed application logs to find stack traces, error
correlations, and temporal patterns around the incident.
"""

from __future__ import annotations

from datetime import timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.agents.tools import search_logs
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import AgentFinding
from src.core.rate_limiter import get_rate_limiter
from src.core.state import InvestigationState

logger = get_logger("logs_agent")

SYSTEM_PROMPT = """\
You are a **Log Forensics Expert** in an incident response team.

Your job is to analyze application logs and identify:
1. Error patterns and their frequency
2. Stack traces that reveal the root cause
3. Temporal correlations (when errors started, what happened just before)
4. Affected services and trace IDs
5. Any anomalies compared to normal operation

Be precise and cite specific log entries as evidence. Include timestamps.
Provide a confidence score (0.0 to 1.0) for your findings.

Respond in this exact JSON format:
{
  "summary": "Brief summary of log findings",
  "evidence": ["evidence point 1", "evidence point 2", ...],
  "confidence": 0.85,
  "relevant_timestamps": ["ISO timestamp 1", "ISO timestamp 2", ...]
}
"""


async def logs_agent_node(state: InvestigationState) -> dict:
    """LangGraph node: Analyze logs for the incident."""
    try:
        settings = get_settings()
        rate_limiter = get_rate_limiter()

        alert = state["alert"]
        mock_data = state["mock_data"]
        plan = state.get("plan")

        # Define search window
        time_end = alert.timestamp + timedelta(minutes=10)
        time_start = alert.timestamp - timedelta(minutes=settings.investigation_time_window_minutes)

        # Gather log data
        error_logs = search_logs(
            mock_data,
            level="ERROR",
            time_start=time_start,
            time_end=time_end,
        )
        warn_logs = search_logs(
            mock_data,
            level="WARN",
            time_start=time_start,
            time_end=time_end,
            limit=20,
        )
        service_logs = search_logs(
            mock_data,
            service=alert.service.value,
            time_start=time_start,
            time_end=time_end,
        )

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
            f"\n## ERROR Logs (all services)\n{error_logs}\n\n"
            f"## WARN Logs\n{warn_logs}\n\n"
            f"## All logs for {alert.service.value}\n{service_logs}\n\n"
            f"Analyze these logs. What is the root cause?"
        )

        # Call LLM
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

        # Parse response
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
            agent_name="logs_agent",
            summary=data.get("summary", "Log analysis completed"),
            evidence=data.get("evidence", []),
            confidence=float(data.get("confidence", 0.5)),
            relevant_timestamps=[],
            raw_data=data,
        )

        logger.info(
            "logs_agent_completed",
            confidence=finding.confidence,
            evidence_count=len(finding.evidence),
        )

        return {
            "findings": [finding],
            "reasoning_trace": [f"[Logs Agent] {finding.summary}"],
        }

    except Exception as e:
        logger.error("logs_agent_failed", error=str(e))
        return {
            "findings": [
                AgentFinding(
                    agent_name="logs_agent",
                    summary=f"Log analysis failed: {e}",
                    confidence=0.0,
                )
            ],
            "agent_errors": [f"logs_agent: {e}"],
            "reasoning_trace": [f"[Logs Agent] FAILED: {e}"],
        }
