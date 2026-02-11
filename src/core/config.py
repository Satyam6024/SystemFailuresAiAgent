from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SFA_",
        case_sensitive=False,
    )

    # ── Groq LLM ────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.1
    groq_max_tokens: int = 4096

    # ── Rate Limiter ────────────────────────────────────────────
    rate_limit_requests_per_minute: int = 30
    rate_limit_burst_size: int = 5

    # ── Agent Behaviour ─────────────────────────────────────────
    investigation_time_window_minutes: int = 60
    max_investigation_duration_seconds: int = 300
    confidence_threshold_for_action: float = 0.7

    # ── Database (Phase 2) ──────────────────────────────────────
    # Default to local SQLite for dev; use PostgreSQL in Docker/production
    database_url: str = "sqlite+aiosqlite:///./sfa.db"

    # ── API (Phase 2) ──────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── GitHub Remediation (Phase 4) ───────────────────────────
    github_token: str = ""
    github_rollback_repo: str = ""
    github_rollback_workflow: str = "rollback.yml"


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
