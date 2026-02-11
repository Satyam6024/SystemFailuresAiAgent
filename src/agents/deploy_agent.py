"""Deploy Intelligence Agent — The Historian.

Maps real-time errors against the timeline of CI/CD deployments
and service configuration changes.
"""

from __future__ import annotations

from datetime import timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.agents.tools import get_deployments
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import AgentFinding
from src.core.rate_limiter import get_rate_limiter
from src.core.state import InvestigationState

logger = get_logger("deploy_agent")

SYSTEM_PROMPT = """\
You are a **Deployment Historian** in an incident response team.

Your job is to analyze recent deployments and configuration changes to determine:
1. Was there a recent deployment to the affected service or its dependencies?
2. What was changed (code deploy, config change, scaling event)?
3. How long before the incident did the deployment happen?
4. Could the deployment be the root cause? (correlation ≠ causation)
5. If no deployments found, state that clearly — this rules out deployment-related causes.

Be precise about timestamps and the gap between deployment and incident.
Provide a confidence score (0.0 to 1.0) for your findings.

Respond in this exact JSON format:
{
  "summary": "Brief summary of deployment findings",
  "evidence": ["evidence point 1", "evidence point 2", ...],
  "confidence": 0.85,
  "relevant_timestamps": ["ISO timestamp 1", "ISO timestamp 2", ...]
}
"""


async def deploy_agent_node(state: InvestigationState) -> dict:
    """LangGraph node: Analyze deployment history for the incident."""
    try:
        settings = get_settings()
        rate_limiter = get_rate_limiter()

        alert = state["alert"]
        mock_data = state["mock_data"]
        plan = state.get("plan")

        time_end = alert.timestamp + timedelta(minutes=5)
        time_start = alert.timestamp - timedelta(minutes=settings.investigation_time_window_minutes)

        # Gather deployment data — all services
        all_deploys = get_deployments(
            mock_data,
            time_start=time_start,
            time_end=time_end,
        )
        # Also check the specific alerted service
        service_deploys = get_deployments(
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
            f"\n## Deployments for {alert.service.value}\n{service_deploys}\n\n"
            f"## All Recent Deployments (all services)\n{all_deploys}\n\n"
            f"Analyze these deployments. Could any of them have caused or contributed to the incident?"
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
            agent_name="deploy_agent",
            summary=data.get("summary", "Deployment analysis completed"),
            evidence=data.get("evidence", []),
            confidence=float(data.get("confidence", 0.5)),
            relevant_timestamps=[],
            raw_data=data,
        )

        logger.info(
            "deploy_agent_completed",
            confidence=finding.confidence,
            evidence_count=len(finding.evidence),
        )

        return {
            "findings": [finding],
            "reasoning_trace": [f"[Deploy Agent] {finding.summary}"],
        }

    except Exception as e:
        logger.error("deploy_agent_failed", error=str(e))
        return {
            "findings": [
                AgentFinding(
                    agent_name="deploy_agent",
                    summary=f"Deployment analysis failed: {e}",
                    confidence=0.0,
                )
            ],
            "agent_errors": [f"deploy_agent: {e}"],
            "reasoning_trace": [f"[Deploy Agent] FAILED: {e}"],
        }
