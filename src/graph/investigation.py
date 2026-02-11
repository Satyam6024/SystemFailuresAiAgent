"""LangGraph investigation graph definition.

Graph structure:
    START → detect → plan → [logs_agent, metrics_agent, deploy_agent] (parallel)
                              → decide → (conditional) → act or report → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.commander import (
    act_node,
    decide_node,
    detect_node,
    plan_node,
    report_node,
    should_act_or_report,
)
from src.agents.deploy_agent import deploy_agent_node
from src.agents.logs_agent import logs_agent_node
from src.agents.metrics_agent import metrics_agent_node
from src.core.state import InvestigationState


def build_investigation_graph() -> StateGraph:
    """Build and compile the investigation graph."""

    graph = StateGraph(InvestigationState)

    # ── Add nodes ───────────────────────────────────────────────
    graph.add_node("detect", detect_node)
    graph.add_node("plan", plan_node)
    graph.add_node("logs_agent", logs_agent_node)
    graph.add_node("metrics_agent", metrics_agent_node)
    graph.add_node("deploy_agent", deploy_agent_node)
    graph.add_node("decide", decide_node)
    graph.add_node("act", act_node)
    graph.add_node("report", report_node)

    # ── Sequential: START → detect → plan ───────────────────────
    graph.add_edge(START, "detect")
    graph.add_edge("detect", "plan")

    # ── Fan-out: plan → three agents in parallel ────────────────
    graph.add_edge("plan", "logs_agent")
    graph.add_edge("plan", "metrics_agent")
    graph.add_edge("plan", "deploy_agent")

    # ── Fan-in: all three agents → decide ───────────────────────
    graph.add_edge("logs_agent", "decide")
    graph.add_edge("metrics_agent", "decide")
    graph.add_edge("deploy_agent", "decide")

    # ── Conditional: decide → act (high confidence) or report ───
    graph.add_conditional_edges(
        "decide",
        should_act_or_report,
        {"act": "act", "report": "report"},
    )

    # ── act → report → END ─────────────────────────────────────
    graph.add_edge("act", "report")
    graph.add_edge("report", END)

    return graph.compile()
