"""Commander Agent — The Orchestrator.

Implements the detect, plan, decide, act, and report node functions
for the LangGraph investigation graph.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import (
    AgentFinding,
    InvestigationPlan,
    InvestigationStatus,
    RCAReport,
    ServiceName,
    TimelineEvent,
)
from src.core.rate_limiter import get_rate_limiter
from src.core.state import InvestigationState

logger = get_logger("commander")


# ── Node: Detect ─────────────────────────────────────────────────


async def detect_node(state: InvestigationState) -> dict:
    """Validate the incoming alert and prepare for investigation."""
    alert = state["alert"]
    logger.info(
        "alert_detected",
        service=alert.service.value,
        metric=alert.metric,
        value=alert.value,
        severity=alert.severity.value,
    )
    return {
        "status": InvestigationStatus.DETECTING,
        "reasoning_trace": [
            f"[Commander] Alert detected: {alert.description} "
            f"(service={alert.service.value}, {alert.metric}={alert.value}, "
            f"threshold={alert.threshold}, severity={alert.severity.value})"
        ],
    }


# ── Node: Plan ───────────────────────────────────────────────────

PLAN_SYSTEM_PROMPT = """\
You are the **Commander** of an incident response team. You have received an alert
and must create an investigation plan.

You have three specialist agents:
1. **Logs Agent** — searches application logs for errors, stack traces, patterns
2. **Metrics Agent** — analyzes performance metrics (CPU, latency, memory, error rates)
3. **Deploy Agent** — reviews recent deployments and configuration changes

Based on the alert, create an investigation plan. Consider:
- What could cause this type of failure?
- Which services should be investigated first?
- What time window is most relevant?

Respond in this exact JSON format:
{
  "hypothesis": "Your initial hypothesis about the root cause",
  "tasks": ["task 1 for agents", "task 2", ...],
  "priority_services": ["service-name-1", "service-name-2"]
}
"""


async def plan_node(state: InvestigationState) -> dict:
    """Create an investigation plan using LLM reasoning."""
    try:
        settings = get_settings()
        rate_limiter = get_rate_limiter()
        alert = state["alert"]

        user_prompt = (
            f"Alert: {alert.description}\n"
            f"Service: {alert.service.value}\n"
            f"Metric: {alert.metric} = {alert.value} (threshold: {alert.threshold})\n"
            f"Severity: {alert.severity.value}\n"
            f"Time: {alert.timestamp.isoformat()}\n\n"
            f"Create an investigation plan."
        )

        await rate_limiter.acquire()
        llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=settings.groq_temperature,
            max_tokens=settings.groq_max_tokens,
        )

        response = await llm.ainvoke([
            SystemMessage(content=PLAN_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            data = {
                "hypothesis": "Unable to parse plan — investigating broadly",
                "tasks": ["Analyze logs", "Check metrics", "Review deployments"],
                "priority_services": [alert.service.value],
            }

        # Validate priority services
        valid_services = [s.value for s in ServiceName]
        priority = [s for s in data.get("priority_services", []) if s in valid_services]
        if not priority:
            priority = [alert.service.value]

        plan = InvestigationPlan(
            hypothesis=data.get("hypothesis", "Unknown"),
            tasks=data.get("tasks", []),
            priority_services=[ServiceName(s) for s in priority],
            time_window_start=alert.timestamp - timedelta(minutes=settings.investigation_time_window_minutes),
            time_window_end=alert.timestamp + timedelta(minutes=10),
        )

        logger.info("plan_created", hypothesis=plan.hypothesis, tasks=len(plan.tasks))

        return {
            "status": InvestigationStatus.PLANNING,
            "plan": plan,
            "reasoning_trace": [
                f"[Commander] Investigation plan created. "
                f"Hypothesis: {plan.hypothesis}. "
                f"Priority services: {[s.value for s in plan.priority_services]}. "
                f"Dispatching Logs, Metrics, and Deploy agents in parallel."
            ],
        }

    except Exception as e:
        logger.error("plan_failed", error=str(e))
        # Fallback plan
        alert = state["alert"]
        plan = InvestigationPlan(
            hypothesis=f"Investigating alert on {alert.service.value}",
            tasks=["Analyze logs", "Check metrics", "Review deployments"],
            priority_services=[alert.service],
            time_window_start=alert.timestamp - timedelta(minutes=60),
            time_window_end=alert.timestamp + timedelta(minutes=10),
        )
        return {
            "status": InvestigationStatus.PLANNING,
            "plan": plan,
            "reasoning_trace": [f"[Commander] Plan creation failed ({e}), using fallback plan."],
        }


# ── Node: Decide ─────────────────────────────────────────────────

DECIDE_SYSTEM_PROMPT = """\
You are the **Commander** of an incident response team. Your three specialist agents
have completed their investigations. Synthesize their findings to determine:

1. **Root Cause** — What is the most likely root cause?
2. **Confidence** — How confident are you? (0.0 to 1.0)
3. **Timeline** — Reconstruct the sequence of events
4. **Recommendation** — What action should be taken?

Consider:
- Do the agents' findings corroborate each other?
- Is there a deployment that correlates with the errors?
- What is the causal chain?

Respond in this exact JSON format:
{
  "root_cause": "Clear description of the root cause",
  "confidence": 0.85,
  "timeline": [
    {"timestamp": "ISO timestamp", "description": "event description", "source": "source"},
    ...
  ],
  "recommendation": "Specific action to take (e.g., rollback deployment X)"
}
"""


async def decide_node(state: InvestigationState) -> dict:
    """Synthesize all agent findings and determine root cause."""
    try:
        settings = get_settings()
        rate_limiter = get_rate_limiter()

        alert = state["alert"]
        plan = state.get("plan")
        findings = state.get("findings", [])

        findings_text = ""
        for f in findings:
            findings_text += (
                f"\n### {f.agent_name} (confidence: {f.confidence})\n"
                f"Summary: {f.summary}\n"
                f"Evidence:\n"
            )
            for e in f.evidence:
                findings_text += f"  - {e}\n"

        user_prompt = (
            f"## Alert\n{alert.description}\n"
            f"Service: {alert.service.value}, {alert.metric}={alert.value}\n\n"
        )
        if plan:
            user_prompt += f"## Initial Hypothesis\n{plan.hypothesis}\n\n"

        user_prompt += f"## Agent Findings\n{findings_text}\n\n"

        if state.get("agent_errors"):
            user_prompt += f"## Agent Errors\n" + "\n".join(state["agent_errors"]) + "\n\n"

        user_prompt += "Synthesize the findings. What is the root cause?"

        await rate_limiter.acquire()
        llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=settings.groq_temperature,
            max_tokens=settings.groq_max_tokens,
        )

        response = await llm.ainvoke([
            SystemMessage(content=DECIDE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            data = {
                "root_cause": response.content[:500],
                "confidence": 0.5,
                "timeline": [],
                "recommendation": "Manual investigation recommended",
            }

        confidence = float(data.get("confidence", 0.5))
        root_cause = data.get("root_cause", "Undetermined")
        recommendation = data.get("recommendation", "Manual investigation recommended")

        logger.info(
            "decision_made",
            root_cause=root_cause[:100],
            confidence=confidence,
            recommendation=recommendation[:100],
        )

        return {
            "status": InvestigationStatus.DECIDING,
            "root_cause": root_cause,
            "confidence": confidence,
            "recommendation": recommendation,
            "reasoning_trace": [
                f"[Commander] Decision: Root cause identified with {confidence:.0%} confidence. "
                f"{root_cause[:200]}"
            ],
        }

    except Exception as e:
        logger.error("decide_failed", error=str(e))
        return {
            "status": InvestigationStatus.DECIDING,
            "root_cause": f"Decision failed: {e}",
            "confidence": 0.0,
            "recommendation": "Manual investigation required",
            "reasoning_trace": [f"[Commander] Decision FAILED: {e}"],
        }


# ── Conditional: Should Act or Report? ──────────────────────────


def should_act_or_report(state: InvestigationState) -> str:
    """Route to 'act' if confidence is high enough, otherwise skip to 'report'."""
    settings = get_settings()
    confidence = state.get("confidence", 0.0)
    if confidence >= settings.confidence_threshold_for_action:
        logger.info("routing_to_act", confidence=confidence)
        return "act"
    logger.info("routing_to_report", confidence=confidence)
    return "report"


# ── Node: Act ────────────────────────────────────────────────────


async def act_node(state: InvestigationState) -> dict:
    """Execute remediation action — triggers GitHub Actions rollback if configured."""
    from src.remediation.github_actions import trigger_rollback

    recommendation = state.get("recommendation", "")
    confidence = state.get("confidence", 0.0)
    alert = state["alert"]
    settings = get_settings()

    action_parts = [f"RECOMMENDED ACTION (confidence={confidence:.0%}): {recommendation}"]
    trace_parts = []

    # Attempt real rollback via GitHub Actions if configured
    if settings.github_token and settings.github_rollback_repo:
        logger.info(
            "attempting_github_rollback",
            service=alert.service.value,
            repo=settings.github_rollback_repo,
        )
        result = await trigger_rollback(
            service=alert.service.value,
            version="previous",
        )
        if result.success:
            action_parts.append(f"ROLLBACK TRIGGERED: {result.message}")
            if result.workflow_url:
                action_parts.append(f"Workflow: {result.workflow_url}")
            trace_parts.append(
                f"[Commander] GitHub Actions rollback triggered for {alert.service.value}. "
                f"{result.message}"
            )
        else:
            action_parts.append(f"ROLLBACK FAILED: {result.message}")
            trace_parts.append(
                f"[Commander] GitHub Actions rollback failed: {result.message}"
            )
    else:
        trace_parts.append(
            "[Commander] GitHub remediation not configured. "
            "Set SFA_GITHUB_TOKEN and SFA_GITHUB_ROLLBACK_REPO to enable automatic rollbacks."
        )

    action = " | ".join(action_parts)
    logger.info("remediation_action", action=action)

    return {
        "status": InvestigationStatus.ACTING,
        "remediation_action": action,
        "reasoning_trace": [f"[Commander] {action_parts[0]}"] + trace_parts,
    }


# ── Node: Report ─────────────────────────────────────────────────


async def report_node(state: InvestigationState) -> dict:
    """Assemble the final RCA report from all state."""
    alert = state["alert"]
    plan = state.get("plan")
    findings = state.get("findings", [])
    root_cause = state.get("root_cause", "Undetermined")
    confidence = state.get("confidence", 0.0)
    recommendation = state.get("recommendation", "")
    remediation = state.get("remediation_action")

    # Build timeline from reasoning trace
    timeline = []
    for trace in state.get("reasoning_trace", []):
        timeline.append(
            TimelineEvent(
                timestamp=datetime.utcnow(),
                description=trace,
                source="reasoning_trace",
            )
        )

    report = RCAReport(
        alert=alert,
        status=InvestigationStatus.COMPLETED,
        plan=plan,
        findings=findings,
        root_cause=root_cause,
        confidence=confidence,
        timeline=timeline,
        recommendation=recommendation,
        remediation_action=remediation,
    )

    logger.info(
        "report_generated",
        investigation_id=report.investigation_id,
        confidence=confidence,
        findings_count=len(findings),
    )

    return {
        "status": InvestigationStatus.REPORTING,
        "report": report,
        "reasoning_trace": [
            f"[Commander] Investigation complete. "
            f"Root cause: {root_cause[:100]}. "
            f"Confidence: {confidence:.0%}. "
            f"Report ID: {report.investigation_id}"
        ],
    }
