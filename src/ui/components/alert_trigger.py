"""Alert trigger component — manual button + scenario dropdown."""

from __future__ import annotations

import streamlit as st

from src.ui.components.api_client import api_post


SCENARIOS = {
    "latent_config_bug": "Latent Config Bug — DB pool exhaustion from config change",
    "memory_leak": "Memory Leak — OOM kill from code deploy",
    "cascading_failure": "Cascading Failure — Database crash cascades upstream",
    "traffic_spike": "Traffic Spike — 10x DDoS-like traffic surge",
}

SEVERITIES = ["critical", "high", "medium", "low"]


def render_alert_trigger():
    """Render the alert trigger controls."""
    st.markdown("### Trigger Investigation")

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        scenario = st.selectbox(
            "Failure Scenario",
            options=list(SCENARIOS.keys()),
            format_func=lambda x: SCENARIOS[x],
            key="trigger_scenario",
        )

    with col2:
        severity = st.selectbox(
            "Severity",
            options=SEVERITIES,
            key="trigger_severity",
        )

    with col3:
        seed = st.number_input(
            "Random Seed",
            value=42,
            min_value=0,
            max_value=9999,
            key="trigger_seed",
        )

    if st.button("🔍 Start Investigation", type="primary", use_container_width=True):
        result = api_post(
            "/api/v1/alert",
            {
                "scenario_type": scenario,
                "seed": seed,
                "severity": severity,
            },
        )
        if result:
            inv_id = result.get("investigation_id", "")
            st.success(f"Investigation started: `{inv_id}`")
            st.session_state["active_investigation_id"] = inv_id
            st.rerun()