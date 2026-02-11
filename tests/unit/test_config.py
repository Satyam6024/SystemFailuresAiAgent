"""Unit tests for src/core/config.py."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.core.config import Settings


class TestSettings:
    def test_default_values(self):
        """Settings should have sensible defaults without any env vars."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
        assert settings.groq_model == "llama-3.3-70b-versatile"
        assert settings.groq_temperature == 0.1
        assert settings.groq_max_tokens == 4096
        assert settings.rate_limit_requests_per_minute == 30
        assert settings.rate_limit_burst_size == 5
        assert settings.investigation_time_window_minutes == 60
        assert settings.confidence_threshold_for_action == 0.7
        assert settings.database_url == "sqlite+aiosqlite:///./sfa.db"
        assert settings.api_port == 8000

    def test_env_override(self):
        """Settings should be overridden by SFA_ prefixed env vars."""
        env = {
            "SFA_GROQ_API_KEY": "test-key-123",
            "SFA_GROQ_MODEL": "llama-3.1-8b-instant",
            "SFA_RATE_LIMIT_REQUESTS_PER_MINUTE": "60",
            "SFA_CONFIDENCE_THRESHOLD_FOR_ACTION": "0.5",
            "SFA_DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
        assert settings.groq_api_key == "test-key-123"
        assert settings.groq_model == "llama-3.1-8b-instant"
        assert settings.rate_limit_requests_per_minute == 60
        assert settings.confidence_threshold_for_action == 0.5
        assert "postgresql" in settings.database_url

    def test_github_settings_default_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
        assert settings.github_token == ""
        assert settings.github_rollback_repo == ""
        assert settings.github_rollback_workflow == "rollback.yml"

    def test_github_settings_from_env(self):
        env = {
            "SFA_GITHUB_TOKEN": "ghp_test123",
            "SFA_GITHUB_ROLLBACK_REPO": "user/repo",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
        assert settings.github_token == "ghp_test123"
        assert settings.github_rollback_repo == "user/repo"