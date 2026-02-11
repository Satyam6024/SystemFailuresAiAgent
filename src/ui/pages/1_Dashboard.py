"""Dashboard page — Service health grid, metric charts, and investigation trigger."""

import streamlit as st

from src.data.mock_generator import MockDataGenerator
from src.data.topology import SERVICE_TOPOLOGY
from src.ui.components.alert_trigger import render_alert_trigger
from src.ui.components.api_client import api_get
from src.ui.components.metric_charts import render_multi_metric_dashboard
from src.ui.components.service_health import render_service_health_grid

st.header("Dashboard")

# ── Health Check ────────────────────────────────────────────────

health = api_get("/health")
if health:
    running = health.get("investigation_running", False)
    current_id = health.get("current_investigation_id")
    if running:
        st.info(f"Investigation in progress: `{current_id}`")
    else:
        st.success("All systems operational — No active investigation")

# ── Service Health Grid ─────────────────────────────────────────

st.subheader("Service Health")

# If there's an active investigation, try to infer service statuses from it
service_statuses = None
if health and health.get("current_investigation_id"):
    inv = api_get(f"/api/v1/investigations/{health['current_investigation_id']}")
    if inv and inv.get("alert"):
        affected_service = inv["alert"]["service"]
        service_statuses = {name: "healthy" for name in SERVICE_TOPOLOGY}
        service_statuses[affected_service] = "degraded"

render_service_health_grid(service_statuses)

# ── Trigger Investigation ───────────────────────────────────────

st.divider()
render_alert_trigger()

# ── Mock Data Preview (metric charts) ───────────────────────────

st.divider()
st.subheader("Metric Preview")
st.caption("Preview of mock data for the selected scenario (before triggering)")

scenario = st.session_state.get("trigger_scenario", "latent_config_bug")
seed = st.session_state.get("trigger_seed", 42)

with st.spinner("Generating mock data preview..."):
    mock_data = MockDataGenerator.generate(scenario, seed=seed)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Log Entries", len(mock_data.logs))
with col2:
    st.metric("Metric Points", len(mock_data.metrics))
with col3:
    st.metric("Deployments", len(mock_data.deployments))

# Show metric charts
available_metrics = sorted(set(p.metric_name for p in mock_data.metrics))
render_multi_metric_dashboard(
    mock_data.metrics,
    metrics=available_metrics[:4],
    thresholds={"p99_latency_ms": 500, "error_rate": 0.05, "memory_mb": 3500},
)