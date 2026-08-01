"""Small Exa API client shared by web research tools."""

from __future__ import annotations

import json
from typing import Any

import requests

from src.config.accessor import get_env_config

EXA_API_BASE = "https://api.exa.ai"
EXA_TIMEOUT = 45


class ExaConfigError(RuntimeError):
    """Raised when Exa is not configured."""


def _api_key() -> str:
    key = get_env_config().data.exa_api_key.strip()
    if not key:
        raise ExaConfigError("EXA_API_KEY is not configured")
    return key


def exa_post(path: str, body: dict[str, Any], *, timeout: int = EXA_TIMEOUT) -> dict[str, Any]:
    """POST a JSON body to Exa and return parsed JSON."""
    resp = requests.post(
        f"{EXA_API_BASE}{path}",
        headers={
            "x-api-key": _api_key(),
            "Content-Type": "application/json",
            "User-Agent": "Vibe-Trading/0.1",
        },
        data=json.dumps(body),
        timeout=timeout,
    )
    if resp.status_code >= 400:
        preview = resp.text[:500]
        raise requests.HTTPError(f"Exa HTTP {resp.status_code}: {preview}", response=resp)
    return resp.json()


def exa_secret_configured() -> bool:
    """Return whether an Exa key is available."""
    return bool(get_env_config().data.exa_api_key.strip())
