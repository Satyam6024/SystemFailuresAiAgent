"""Configuration page — Tune alert thresholds, agent parameters, and mock data settings."""

import streamlit as st

st.header("Configuration")

st.caption(
    "These settings are stored in session state and affect subsequent investigations. "
    "For persistent configuration, edit the `.env` file."
)

# ── Initialize defaults ─────────────────────────────────────────

defaults = {
    "config_latency_threshold": 500.0,
    "config_error_rate_threshold": 0.05,
    "config_memory_threshold": 3500.0,
    "config_cpu_threshold": 90.0,
    "config_temperature": 0.1,
    "config_max_tokens": 4096,
    "config_time_window": 60,
    "config_confidence_threshold": 0.7,
    "config_scenario": "latent_config_bug",
    "config_severity": "critical",
    "config_seed": 42,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ── Alert Thresholds ────────────────────────────────────────────

st.subheader("Alert Thresholds")
st.caption("When a metric exceeds these thresholds, an alert is triggered.")

col1, col2 = st.columns(2)
with col1:
    st.number_input(
        "p99 Latency Threshold (ms)",
        min_value=50.0,
        max_value=10000.0,
        step=50.0,
        key="config_latency_threshold",
    )
    st.number_input(
        "Memory Threshold (MB)",
        min_value=512.0,
        max_value=16000.0,
        step=256.0,
        key="config_memory_threshold",
    )

with col2:
    st.number_input(
        "Error Rate Threshold",
        min_value=0.001,
        max_value=1.0,
        step=0.01,
        format="%.3f",
        key="config_error_rate_threshold",
    )
    st.number_input(
        "CPU Threshold (%)",
        min_value=10.0,
        max_value=100.0,
        step=5.0,
        key="config_cpu_threshold",
    )

# ── Agent Parameters ────────────────────────────────────────────

st.divider()
st.subheader("Agent Parameters")
st.caption("Controls how the LLM agents reason and respond.")

col1, col2 = st.columns(2)
with col1:
    st.slider(
        "LLM Temperature",
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        key="config_temperature",
        help="Lower = more deterministic, Higher = more creative",
    )
    st.number_input(
        "Investigation Time Window (minutes)",
        min_value=5,
        max_value=360,
        step=5,
        key="config_time_window",
        help="How far back agents look for evidence",
    )

with col2:
    st.number_input(
        "Max Tokens per LLM Call",
        min_value=256,
        max_value=8192,
        step=256,
        key="config_max_tokens",
    )
    st.slider(
        "Confidence Threshold for Action",
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        key="config_confidence_threshold",
        help="Minimum confidence to trigger remediation",
    )

# ── Mock Data Settings ──────────────────────────────────────────

st.divider()
st.subheader("Mock Data Settings")
st.caption("Controls which failure scenario is simulated and how data is generated.")

col1, col2, col3 = st.columns(3)
with col1:
    st.selectbox(
        "Default Scenario",
        options=["latent_config_bug", "memory_leak", "cascading_failure", "traffic_spike"],
        key="config_scenario",
    )
with col2:
    st.selectbox(
        "Default Severity",
        options=["critical", "high", "medium", "low"],
        key="config_severity",
    )
with col3:
    st.number_input(
        "Default Random Seed",
        min_value=0,
        max_value=9999,
        key="config_seed",
    )

# ── Current Config Summary ──────────────────────────────────────

st.divider()
st.subheader("Current Configuration")

config_summary = {
    "Alert Thresholds": {
        "p99_latency_ms": st.session_state.config_latency_threshold,
        "error_rate": st.session_state.config_error_rate_threshold,
        "memory_mb": st.session_state.config_memory_threshold,
        "cpu_percent": st.session_state.config_cpu_threshold,
    },
    "Agent Parameters": {
        "temperature": st.session_state.config_temperature,
        "max_tokens": st.session_state.config_max_tokens,
        "time_window_minutes": st.session_state.config_time_window,
        "confidence_threshold": st.session_state.config_confidence_threshold,
    },
    "Mock Data": {
        "scenario": st.session_state.config_scenario,
        "severity": st.session_state.config_severity,
        "seed": st.session_state.config_seed,
    },
}

st.json(config_summary)