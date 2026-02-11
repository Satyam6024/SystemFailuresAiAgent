"""Integration test for the full LangGraph investigation flow.

Mocks the Groq LLM so we can test the full graph pipeline without API calls.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models import (
    AgentFinding,
    InvestigationPlan,
    InvestigationStatus,
    MockDataSet,
    RCAReport,
    ServiceName,
    Severity,
)
from src.data.mock_generator import MockDataGenerator


def _make_mock_llm_response(content: str):
    """Create a mock LLM response object."""
    resp = MagicMock()
    resp.content = content
    return resp


def _mock_plan_response():
    return _make_mock_llm_response(json.dumps({
        "hypothesis": "DB connection pool exhausted due to config change",
        "tasks": [
            "Check checkout-service logs for connection errors",
            "Monitor DB connection pool metrics",
            "Review recent config deployments",
        ],
        "priority_services": ["checkout-service", "postgres-db"],
    }))


def _mock_logs_response():
    return _make_mock_llm_response(json.dumps({
        "summary": "Found 20+ DB connection timeout errors in checkout-service starting 5 minutes before alert",
        "evidence": [
            "20 DB connection timeout errors in last 5 minutes",
            "Pool exhausted: active=10/10 (was 100 before config change)",
            "502 Bad Gateway errors on api-gateway correlate with checkout-service timeouts",
        ],
        "confidence": 0.90,
        "relevant_timestamps": [],
    }))


def _mock_metrics_response():
    return _make_mock_llm_response(json.dumps({
        "summary": "p99 latency spike from 120ms to 2000ms on checkout-service, correlated with connections maxing at 10",
        "evidence": [
            "checkout-service p99_latency_ms jumped from ~120ms to 2000ms at T-5min",
            "connections_active stuck at 10 (new max_connections limit)",
            "api-gateway error_rate increased to 15%",
        ],
        "confidence": 0.88,
        "relevant_timestamps": [],
    }))


def _mock_deploy_response():
    return _make_mock_llm_response(json.dumps({
        "summary": "Config deployment to checkout-service 15 minutes before incident reduced DB pool from 100 to 10",
        "evidence": [
            "deploy-XXXX at T-15min: config_change 'Updated db_pool_config: max_connections 100 -> 10'",
            "This directly explains the connection pool exhaustion",
        ],
        "confidence": 0.95,
        "relevant_timestamps": [],
    }))


def _mock_decide_response():
    return _make_mock_llm_response(json.dumps({
        "root_cause": "A configuration deployment 15 minutes before the incident reduced the DB connection pool from 100 to 10 connections, causing pool exhaustion under normal load",
        "confidence": 0.92,
        "timeline": [
            {"timestamp": "2025-01-15T10:15:00", "description": "Config deployed reducing max_connections to 10", "source": "deploy_agent"},
            {"timestamp": "2025-01-15T10:25:00", "description": "Connection pool starts exhausting under load", "source": "metrics_agent"},
            {"timestamp": "2025-01-15T10:30:00", "description": "Latency spike and timeout errors", "source": "logs_agent"},
        ],
        "recommendation": "Immediately rollback the config change to restore max_connections to 100",
    }))


# Track which call number we're on to return different responses
_call_count = 0


def _side_effect_factory():
    """Create a side_effect function that returns different responses based on call order."""
    responses = [
        _mock_plan_response(),     # plan_node
        _mock_logs_response(),     # logs_agent_node
        _mock_metrics_response(),  # metrics_agent_node
        _mock_deploy_response(),   # deploy_agent_node
        _mock_decide_response(),   # decide_node
    ]
    call_idx = {"idx": 0}

    async def mock_ainvoke(messages, **kwargs):
        idx = call_idx["idx"]
        call_idx["idx"] += 1
        if idx < len(responses):
            return responses[idx]
        return _make_mock_llm_response('{"summary": "fallback", "confidence": 0.5}')

    return mock_ainvoke


class TestFullGraphFlow:
    @pytest.mark.asyncio
    async def test_end_to_end_investigation(self):
        """Run the full graph with mocked LLM and verify the pipeline."""
        # Generate mock data
        fixed_time = datetime(2025, 1, 15, 10, 30, 0)
        mock_data = MockDataGenerator.generate(
            "latent_config_bug", seed=42, incident_time=fixed_time
        )

        # Mock settings to avoid needing real API key
        mock_settings = MagicMock()
        mock_settings.groq_api_key = "test-key"
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        mock_settings.groq_temperature = 0.1
        mock_settings.groq_max_tokens = 4096
        mock_settings.investigation_time_window_minutes = 60
        mock_settings.confidence_threshold_for_action = 0.7
        mock_settings.github_token = ""
        mock_settings.github_rollback_repo = ""

        # Create a mock LLM instance
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=_side_effect_factory())

        with patch("src.agents.commander.get_settings", return_value=mock_settings), \
             patch("src.agents.commander.get_rate_limiter") as mock_rl, \
             patch("src.agents.logs_agent.get_settings", return_value=mock_settings), \
             patch("src.agents.logs_agent.get_rate_limiter") as mock_rl2, \
             patch("src.agents.metrics_agent.get_settings", return_value=mock_settings), \
             patch("src.agents.metrics_agent.get_rate_limiter") as mock_rl3, \
             patch("src.agents.deploy_agent.get_settings", return_value=mock_settings), \
             patch("src.agents.deploy_agent.get_rate_limiter") as mock_rl4, \
             patch("src.agents.commander.ChatGroq", return_value=mock_llm), \
             patch("src.agents.logs_agent.ChatGroq", return_value=mock_llm), \
             patch("src.agents.metrics_agent.ChatGroq", return_value=mock_llm), \
             patch("src.agents.deploy_agent.ChatGroq", return_value=mock_llm):

            # Make rate limiters no-op
            for rl in [mock_rl, mock_rl2, mock_rl3, mock_rl4]:
                rl_instance = AsyncMock()
                rl_instance.acquire = AsyncMock()
                rl.return_value = rl_instance

            from src.graph.investigation import build_investigation_graph

            graph = build_investigation_graph()

            initial_state = {
                "alert": mock_data.alert,
                "mock_data": mock_data,
                "status": InvestigationStatus.DETECTING,
                "plan": None,
                "root_cause": None,
                "recommendation": None,
                "confidence": 0.0,
                "findings": [],
                "agent_errors": [],
                "reasoning_trace": [],
                "report": None,
                "remediation_action": None,
                "iteration": 0,
            }

            result = await graph.ainvoke(initial_state)

        # Verify the pipeline completed
        assert result["report"] is not None
        report = result["report"]
        assert isinstance(report, RCAReport)

        # Verify findings from all 3 agents
        findings = result["findings"]
        assert len(findings) == 3
        agent_names = {f.agent_name for f in findings}
        assert "logs_agent" in agent_names
        assert "metrics_agent" in agent_names
        assert "deploy_agent" in agent_names

        # Verify decision results
        assert result["root_cause"] is not None
        assert result["confidence"] > 0.7
        assert result["recommendation"] is not None

        # Verify reasoning trace has entries from all stages
        trace = result["reasoning_trace"]
        assert len(trace) > 0
        trace_text = " ".join(trace)
        assert "Commander" in trace_text
        assert "Logs Agent" in trace_text
        assert "Metrics Agent" in trace_text
        assert "Deploy Agent" in trace_text

    @pytest.mark.asyncio
    async def test_graph_handles_llm_failure_gracefully(self):
        """Graph should still complete even if LLM calls fail."""
        fixed_time = datetime(2025, 1, 15, 10, 30, 0)
        mock_data = MockDataGenerator.generate(
            "latent_config_bug", seed=42, incident_time=fixed_time
        )

        mock_settings = MagicMock()
        mock_settings.groq_api_key = ""
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        mock_settings.groq_temperature = 0.1
        mock_settings.groq_max_tokens = 4096
        mock_settings.investigation_time_window_minutes = 60
        mock_settings.confidence_threshold_for_action = 0.7
        mock_settings.github_token = ""
        mock_settings.github_rollback_repo = ""

        # LLM that always raises
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API key invalid"))

        with patch("src.agents.commander.get_settings", return_value=mock_settings), \
             patch("src.agents.commander.get_rate_limiter") as mock_rl, \
             patch("src.agents.logs_agent.get_settings", return_value=mock_settings), \
             patch("src.agents.logs_agent.get_rate_limiter") as mock_rl2, \
             patch("src.agents.metrics_agent.get_settings", return_value=mock_settings), \
             patch("src.agents.metrics_agent.get_rate_limiter") as mock_rl3, \
             patch("src.agents.deploy_agent.get_settings", return_value=mock_settings), \
             patch("src.agents.deploy_agent.get_rate_limiter") as mock_rl4, \
             patch("src.agents.commander.ChatGroq", return_value=mock_llm), \
             patch("src.agents.logs_agent.ChatGroq", return_value=mock_llm), \
             patch("src.agents.metrics_agent.ChatGroq", return_value=mock_llm), \
             patch("src.agents.deploy_agent.ChatGroq", return_value=mock_llm):

            for rl in [mock_rl, mock_rl2, mock_rl3, mock_rl4]:
                rl_instance = AsyncMock()
                rl_instance.acquire = AsyncMock()
                rl.return_value = rl_instance

            from src.graph.investigation import build_investigation_graph

            graph = build_investigation_graph()

            initial_state = {
                "alert": mock_data.alert,
                "mock_data": mock_data,
                "status": InvestigationStatus.DETECTING,
                "plan": None,
                "root_cause": None,
                "recommendation": None,
                "confidence": 0.0,
                "findings": [],
                "agent_errors": [],
                "reasoning_trace": [],
                "report": None,
                "remediation_action": None,
                "iteration": 0,
            }

            # Should NOT raise — graceful degradation
            result = await graph.ainvoke(initial_state)

        # Graph should complete with a report
        assert result["report"] is not None
        # All agents should have findings (even if low confidence due to failure)
        assert len(result["findings"]) == 3
        # Errors should be recorded
        assert len(result["agent_errors"]) > 0


class TestConditionalRouting:
    def test_high_confidence_routes_to_act(self):
        """Confidence above threshold should route to 'act'."""
        from src.agents.commander import should_act_or_report

        mock_settings = MagicMock()
        mock_settings.confidence_threshold_for_action = 0.7

        state = {"confidence": 0.85}
        with patch("src.agents.commander.get_settings", return_value=mock_settings):
            result = should_act_or_report(state)
        assert result == "act"

    def test_low_confidence_routes_to_report(self):
        """Confidence below threshold should route to 'report'."""
        from src.agents.commander import should_act_or_report

        mock_settings = MagicMock()
        mock_settings.confidence_threshold_for_action = 0.7

        state = {"confidence": 0.3}
        with patch("src.agents.commander.get_settings", return_value=mock_settings):
            result = should_act_or_report(state)
        assert result == "report"

    def test_exact_threshold_routes_to_act(self):
        """Confidence exactly at threshold should route to 'act'."""
        from src.agents.commander import should_act_or_report

        mock_settings = MagicMock()
        mock_settings.confidence_threshold_for_action = 0.7

        state = {"confidence": 0.7}
        with patch("src.agents.commander.get_settings", return_value=mock_settings):
            result = should_act_or_report(state)
        assert result == "act"