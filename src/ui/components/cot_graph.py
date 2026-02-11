"""Chain-of-Thought graph visualization using streamlit-agraph."""

from __future__ import annotations

from typing import Optional

import streamlit as st

# Try streamlit-agraph, fall back to graphviz
_USE_AGRAPH = True
try:
    from streamlit_agraph import agraph, Config, Edge, Node
except ImportError:
    _USE_AGRAPH = False


# Node definitions for the investigation graph
GRAPH_NODES = [
    ("detect", "Detect"),
    ("plan", "Plan"),
    ("logs_agent", "Logs Agent"),
    ("metrics_agent", "Metrics Agent"),
    ("deploy_agent", "Deploy Agent"),
    ("decide", "Decide"),
    ("act", "Act"),
    ("report", "Report"),
]

GRAPH_EDGES = [
    ("detect", "plan"),
    ("plan", "logs_agent"),
    ("plan", "metrics_agent"),
    ("plan", "deploy_agent"),
    ("logs_agent", "decide"),
    ("metrics_agent", "decide"),
    ("deploy_agent", "decide"),
    ("decide", "act"),
    ("decide", "report"),
    ("act", "report"),
]

# Status to color mapping
STATUS_COLORS = {
    "pending": "#bdc3c7",
    "active": "#3498db",
    "completed": "#2ecc71",
    "error": "#e74c3c",
    "skipped": "#95a5a6",
}


def _infer_node_statuses(investigation_data: dict) -> dict[str, str]:
    """Infer node statuses from investigation state."""
    status = investigation_data.get("status", "detecting")
    findings = investigation_data.get("findings", [])
    agent_errors = investigation_data.get("agent_errors", [])
    has_act = investigation_data.get("remediation_action") is not None

    statuses = {node_id: "pending" for node_id, _ in GRAPH_NODES}

    # Map investigation status to node progression
    status_progression = {
        "detecting": ["detect"],
        "investigating": ["detect", "plan"],
        "planning": ["detect", "plan"],
        "deciding": ["detect", "plan", "logs_agent", "metrics_agent", "deploy_agent"],
        "acting": ["detect", "plan", "logs_agent", "metrics_agent", "deploy_agent", "decide"],
        "reporting": ["detect", "plan", "logs_agent", "metrics_agent", "deploy_agent", "decide"],
        "completed": ["detect", "plan", "logs_agent", "metrics_agent", "deploy_agent", "decide", "report"],
        "failed": ["detect"],
    }

    completed_nodes = status_progression.get(status, [])
    for node_id in completed_nodes:
        statuses[node_id] = "completed"

    # Mark active node
    if status == "detecting":
        statuses["detect"] = "active"
    elif status == "investigating" or status == "planning":
        statuses["plan"] = "active"
        statuses["detect"] = "completed"
    elif status == "deciding":
        statuses["decide"] = "active"
    elif status == "acting":
        statuses["act"] = "active"
        statuses["decide"] = "completed"
    elif status == "reporting":
        statuses["report"] = "active"
    elif status == "completed":
        if has_act:
            statuses["act"] = "completed"
        else:
            statuses["act"] = "skipped"

    # Check agent errors
    agent_error_names = set()
    for err in agent_errors:
        if "logs_agent" in err:
            agent_error_names.add("logs_agent")
        if "metrics_agent" in err:
            agent_error_names.add("metrics_agent")
        if "deploy_agent" in err:
            agent_error_names.add("deploy_agent")

    for name in agent_error_names:
        statuses[name] = "error"

    # If we have findings, those agents completed
    for f in findings:
        agent = f.get("agent_name", "")
        if agent in statuses and agent not in agent_error_names:
            statuses[agent] = "completed"

    return statuses


def render_cot_graph_agraph(investigation_data: dict):
    """Render the CoT graph using streamlit-agraph."""
    node_statuses = _infer_node_statuses(investigation_data)

    nodes = []
    for node_id, label in GRAPH_NODES:
        status = node_statuses.get(node_id, "pending")
        color = STATUS_COLORS.get(status, "#bdc3c7")
        nodes.append(Node(
            id=node_id,
            label=label,
            color=color,
            size=25,
            font={"color": "#ffffff" if status != "pending" else "#333333"},
        ))

    edges = []
    for source, target in GRAPH_EDGES:
        src_status = node_statuses.get(source, "pending")
        edge_color = "#2ecc71" if src_status == "completed" else "#ddd"
        edges.append(Edge(
            source=source,
            target=target,
            color=edge_color,
            width=2 if src_status == "completed" else 1,
        ))

    config = Config(
        width=700,
        height=400,
        directed=True,
        hierarchical=True,
        physics=False,
        nodeHighlightBehavior=True,
        highlightColor="#f1c40f",
    )

    agraph(nodes=nodes, edges=edges, config=config)


def render_cot_graph_graphviz(investigation_data: dict):
    """Fallback: render the CoT graph using Graphviz."""
    node_statuses = _infer_node_statuses(investigation_data)

    dot_lines = [
        "digraph investigation {",
        '  rankdir=TB;',
        '  node [shape=box, style="rounded,filled", fontname="Arial"];',
        '  edge [fontname="Arial"];',
    ]

    for node_id, label in GRAPH_NODES:
        status = node_statuses.get(node_id, "pending")
        color = STATUS_COLORS.get(status, "#bdc3c7")
        font_color = "white" if status != "pending" else "black"
        dot_lines.append(
            f'  {node_id} [label="{label}", fillcolor="{color}", fontcolor="{font_color}"];'
        )

    # Group parallel agents on same rank
    dot_lines.append('  { rank=same; logs_agent; metrics_agent; deploy_agent; }')

    for source, target in GRAPH_EDGES:
        src_status = node_statuses.get(source, "pending")
        color = "#2ecc71" if src_status == "completed" else "#cccccc"
        dot_lines.append(f'  {source} -> {target} [color="{color}"];')

    dot_lines.append("}")
    dot_source = "\n".join(dot_lines)

    st.graphviz_chart(dot_source)


def render_cot_graph(investigation_data: dict):
    """Render the Chain-of-Thought graph with best available library."""
    if _USE_AGRAPH:
        try:
            render_cot_graph_agraph(investigation_data)
            return
        except Exception:
            pass
    render_cot_graph_graphviz(investigation_data)


def render_status_legend():
    """Render a color legend for graph node statuses."""
    cols = st.columns(5)
    for col, (status, color) in zip(cols, STATUS_COLORS.items()):
        with col:
            st.markdown(
                f'<span style="display:inline-block;width:12px;height:12px;'
                f'background:{color};border-radius:50%;margin-right:4px;"></span>'
                f'<small>{status.title()}</small>',
                unsafe_allow_html=True,
            )