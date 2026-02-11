"""Shared HTTP client for Streamlit pages to talk to the FastAPI backend."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
import streamlit as st

_DEFAULT_API_URL = os.environ.get("SFA_API_URL", "http://127.0.0.1:8000")


def _base_url() -> str:
    return st.session_state.get("api_url", _DEFAULT_API_URL)


def api_get(path: str, **params) -> dict | list | str | None:
    """GET request to the API. Returns parsed JSON or None on error."""
    try:
        r = httpx.get(f"{_base_url()}{path}", params=params, timeout=10)
        if r.status_code == 200:
            content_type = r.headers.get("content-type", "")
            if "text/" in content_type:
                return r.text
            return r.json()
        return None
    except httpx.ConnectError:
        st.error("Cannot connect to API. Is the FastAPI server running?")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_get_bytes(path: str) -> bytes | None:
    """GET request that returns raw bytes (for PDF downloads)."""
    try:
        r = httpx.get(f"{_base_url()}{path}", timeout=30)
        if r.status_code == 200:
            return r.content
        return None
    except httpx.ConnectError:
        st.error("Cannot connect to API. Is the FastAPI server running?")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, json_body: dict) -> dict | None:
    """POST request to the API. Returns parsed JSON or None on error."""
    try:
        r = httpx.post(f"{_base_url()}{path}", json=json_body, timeout=10)
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 409:
            st.warning(r.json().get("detail", "Investigation already running"))
            return None
        st.error(f"API returned {r.status_code}: {r.text}")
        return None
    except httpx.ConnectError:
        st.error("Cannot connect to API. Is the FastAPI server running?")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None