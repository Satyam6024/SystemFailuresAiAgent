"""Service health grid component — 8-cell colored grid showing service status."""

from __future__ import annotations

import streamlit as st

from src.data.topology import SERVICE_TOPOLOGY


def _status_color(status: str) -> str:
    return {"healthy": "#2ecc71", "degraded": "#f39c12", "down": "#e74c3c"}.get(
        status, "#95a5a6"
    )


def _status_emoji(status: str) -> str:
    return {"healthy": "✅", "degraded": "⚠️", "down": "🔴"}.get(status, "❓")


def render_service_health_grid(service_statuses: dict[str, str] | None = None):
    """Render an 8-cell grid of service health indicators.

    Args:
        service_statuses: Dict mapping service name to status
                         ("healthy", "degraded", "down").
                         If None, all services shown as healthy.
    """
    if service_statuses is None:
        service_statuses = {name: "healthy" for name in SERVICE_TOPOLOGY}

    cols = st.columns(4)
    for i, (name, info) in enumerate(SERVICE_TOPOLOGY.items()):
        status = service_statuses.get(name, "healthy")
        color = _status_color(status)
        emoji = _status_emoji(status)

        with cols[i % 4]:
            st.markdown(
                f"""
                <div style="
                    border: 2px solid {color};
                    border-radius: 8px;
                    padding: 12px;
                    margin: 4px 0;
                    background: {color}15;
                    text-align: center;
                ">
                    <div style="font-size: 1.3em;">{emoji}</div>
                    <div style="font-weight: bold; font-size: 0.85em;">{name}</div>
                    <div style="color: {color}; font-size: 0.75em; text-transform: uppercase;">{status}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )