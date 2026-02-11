"""GitHub Actions Remediation — Trigger rollback workflows via GitHub API.

Uses the GitHub REST API to dispatch a workflow_dispatch event on a
configured repository, passing the service name and target version
as inputs to the rollback workflow.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger("remediation.github")

GITHUB_API_BASE = "https://api.github.com"


@dataclass
class RollbackResult:
    """Result of a rollback trigger attempt."""

    success: bool
    message: str
    workflow_url: str | None = None
    status_code: int | None = None


async def trigger_rollback(
    service: str,
    version: str = "previous",
    ref: str = "main",
) -> RollbackResult:
    """Trigger a GitHub Actions rollback workflow.

    Calls POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches
    with the service and version as workflow inputs.

    Args:
        service: Name of the service to roll back (e.g., "checkout-service").
        version: Target version to roll back to (default: "previous").
        ref: Git ref to run the workflow on (default: "main").

    Returns:
        RollbackResult with success status and details.
    """
    settings = get_settings()

    if not settings.github_token:
        logger.warning("github_token_not_configured")
        return RollbackResult(
            success=False,
            message="GitHub token not configured. Set SFA_GITHUB_TOKEN in .env to enable rollbacks.",
        )

    if not settings.github_rollback_repo:
        logger.warning("github_rollback_repo_not_configured")
        return RollbackResult(
            success=False,
            message="GitHub rollback repo not configured. Set SFA_GITHUB_ROLLBACK_REPO in .env.",
        )

    repo = settings.github_rollback_repo  # e.g., "owner/repo"
    workflow = settings.github_rollback_workflow  # e.g., "rollback.yml"

    url = f"{GITHUB_API_BASE}/repos/{repo}/actions/workflows/{workflow}/dispatches"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "ref": ref,
        "inputs": {
            "service": service,
            "target_version": version,
            "triggered_by": "system-failures-ai-agent",
        },
    }

    logger.info(
        "triggering_rollback",
        repo=repo,
        workflow=workflow,
        service=service,
        version=version,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code == 204:
            workflow_url = f"https://github.com/{repo}/actions/workflows/{workflow}"
            logger.info(
                "rollback_triggered",
                service=service,
                version=version,
                workflow_url=workflow_url,
            )
            return RollbackResult(
                success=True,
                message=f"Rollback triggered for {service} to version '{version}'.",
                workflow_url=workflow_url,
                status_code=204,
            )

        logger.error(
            "rollback_failed",
            status_code=response.status_code,
            body=response.text[:500],
        )
        return RollbackResult(
            success=False,
            message=f"GitHub API returned {response.status_code}: {response.text[:200]}",
            status_code=response.status_code,
        )

    except httpx.HTTPError as e:
        logger.error("rollback_http_error", error=str(e))
        return RollbackResult(
            success=False,
            message=f"HTTP error triggering rollback: {e}",
        )


async def check_workflow_status(repo: str | None = None) -> dict:
    """Check if the rollback workflow exists and is accessible.

    Returns a dict with 'accessible', 'workflow_name', and 'error' keys.
    """
    settings = get_settings()
    repo = repo or settings.github_rollback_repo

    if not settings.github_token or not repo:
        return {
            "accessible": False,
            "workflow_name": None,
            "error": "GitHub token or repo not configured",
        }

    workflow = settings.github_rollback_workflow
    url = f"{GITHUB_API_BASE}/repos/{repo}/actions/workflows/{workflow}"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return {
                "accessible": True,
                "workflow_name": data.get("name", workflow),
                "error": None,
            }

        return {
            "accessible": False,
            "workflow_name": None,
            "error": f"GitHub API returned {response.status_code}",
        }

    except httpx.HTTPError as e:
        return {
            "accessible": False,
            "workflow_name": None,
            "error": str(e),
        }