"""Unit tests for src/remediation/github_actions.py."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.remediation.github_actions import RollbackResult, trigger_rollback, check_workflow_status


class TestRollbackResult:
    def test_create_success(self):
        r = RollbackResult(success=True, message="Rollback triggered")
        assert r.success is True
        assert r.workflow_url is None
        assert r.status_code is None

    def test_create_with_all_fields(self):
        r = RollbackResult(
            success=True,
            message="OK",
            workflow_url="https://github.com/user/repo/actions",
            status_code=204,
        )
        assert r.workflow_url is not None
        assert r.status_code == 204


class TestTriggerRollback:
    @pytest.mark.asyncio
    async def test_no_token_returns_failure(self):
        """Without a GitHub token, rollback should fail gracefully."""
        mock_settings = MagicMock()
        mock_settings.github_token = ""
        mock_settings.github_rollback_repo = "user/repo"

        with patch("src.remediation.github_actions.get_settings", return_value=mock_settings):
            result = await trigger_rollback("checkout-service")

        assert result.success is False
        assert "token not configured" in result.message.lower()

    @pytest.mark.asyncio
    async def test_no_repo_returns_failure(self):
        mock_settings = MagicMock()
        mock_settings.github_token = "ghp_test"
        mock_settings.github_rollback_repo = ""

        with patch("src.remediation.github_actions.get_settings", return_value=mock_settings):
            result = await trigger_rollback("checkout-service")

        assert result.success is False
        assert "repo not configured" in result.message.lower()

    @pytest.mark.asyncio
    async def test_successful_rollback(self):
        mock_settings = MagicMock()
        mock_settings.github_token = "ghp_test123"
        mock_settings.github_rollback_repo = "user/repo"
        mock_settings.github_rollback_workflow = "rollback.yml"

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("src.remediation.github_actions.get_settings", return_value=mock_settings), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await trigger_rollback("checkout-service", version="v1.0.0")

        assert result.success is True
        assert result.status_code == 204
        assert "checkout-service" in result.message

    @pytest.mark.asyncio
    async def test_api_error(self):
        mock_settings = MagicMock()
        mock_settings.github_token = "ghp_test123"
        mock_settings.github_rollback_repo = "user/repo"
        mock_settings.github_rollback_workflow = "rollback.yml"

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("src.remediation.github_actions.get_settings", return_value=mock_settings), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await trigger_rollback("checkout-service")

        assert result.success is False
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_http_error(self):
        mock_settings = MagicMock()
        mock_settings.github_token = "ghp_test123"
        mock_settings.github_rollback_repo = "user/repo"
        mock_settings.github_rollback_workflow = "rollback.yml"

        with patch("src.remediation.github_actions.get_settings", return_value=mock_settings), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await trigger_rollback("checkout-service")

        assert result.success is False
        assert "HTTP error" in result.message or "Connection" in result.message


class TestCheckWorkflowStatus:
    @pytest.mark.asyncio
    async def test_no_config_returns_inaccessible(self):
        mock_settings = MagicMock()
        mock_settings.github_token = ""
        mock_settings.github_rollback_repo = ""

        with patch("src.remediation.github_actions.get_settings", return_value=mock_settings):
            result = await check_workflow_status()

        assert result["accessible"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_successful_check(self):
        mock_settings = MagicMock()
        mock_settings.github_token = "ghp_test"
        mock_settings.github_rollback_repo = "user/repo"
        mock_settings.github_rollback_workflow = "rollback.yml"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Service Rollback"}

        with patch("src.remediation.github_actions.get_settings", return_value=mock_settings), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await check_workflow_status()

        assert result["accessible"] is True
        assert result["workflow_name"] == "Service Rollback"