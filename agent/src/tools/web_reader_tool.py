"""URL reader backed by Exa Contents."""

from __future__ import annotations

import ipaddress
import json
import logging
from urllib.parse import urlsplit

from src.agent.progress import emit_progress
from src.agent.tools import BaseTool
from src.security.scanner import with_security_warnings
from src.tools._exa_client import ExaConfigError, exa_post, exa_secret_configured

logger = logging.getLogger(__name__)

_MAX_LENGTH = 12000


def _url_allowed(url: str) -> tuple[bool, str]:
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return False, "target URL is not allowed"

    if parsed.scheme.lower() not in {"http", "https"}:
        return False, "target URL is not allowed"
    if not parsed.hostname:
        return False, "target URL is not allowed"
    if parsed.username or parsed.password:
        return False, "target URL is not allowed"

    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return False, "target URL is not allowed"

    try:
        ip = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return True, ""

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    ):
        return False, "target URL is not allowed"
    return True, ""


def read_url(url: str, no_cache: bool = False) -> str:
    target_url = url.strip()
    allowed, error = _url_allowed(target_url)
    if not allowed:
        return json.dumps({"status": "error", "tool": "read_url", "error": error}, ensure_ascii=False)

    try:
        emit_progress("fetching", message=f"Exa contents {target_url[:60]}")
        data = exa_post(
            "/contents",
            {
                "urls": [target_url],
                "text": True,
                "highlights": True,
                "summary": {"query": "Summarize the page for financial research."},
                "maxAgeHours": 0 if no_cache else 24,
            },
            timeout=45,
        )
    except ExaConfigError as exc:
        return json.dumps({"status": "error", "tool": "read_url", "error": str(exc)}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Exa contents failed: %s", exc)
        return json.dumps({"status": "error", "tool": "read_url", "error": str(exc)}, ensure_ascii=False)

    results = data.get("results") or []
    if not results:
        return json.dumps(
            {
                "status": "error",
                "tool": "read_url",
                "error": "Exa returned no content for the URL",
                "statuses": data.get("statuses") or [],
            },
            ensure_ascii=False,
        )

    item = results[0]
    text = item.get("text") or ""
    original_length = len(text)
    if len(text) > _MAX_LENGTH:
        text = text[:_MAX_LENGTH] + f"\n\n... (truncated, total {original_length} chars)"

    payload = {
        "status": "ok",
        "tool": "read_url",
        "provider": "exa",
        "title": item.get("title", ""),
        "url": item.get("url") or target_url,
        "published_date": item.get("publishedDate"),
        "author": item.get("author"),
        "summary": item.get("summary"),
        "highlights": (item.get("highlights") or [])[:5],
        "content": text,
        "length": original_length,
        "statuses": data.get("statuses") or [],
        "request_id": data.get("requestId"),
    }
    payload = with_security_warnings(
        payload,
        fields=("title", "summary", "highlights.*", "content"),
    )
    return json.dumps(payload, ensure_ascii=False)


class WebReaderTool(BaseTool):
    """Read webpage content with Exa Contents."""

    name = "read_url"

    @classmethod
    def check_available(cls) -> bool:
        return exa_secret_configured()

    description = (
        "Fetch webpage text, metadata, highlights, and summary via Exa Contents. "
        "Use after web_search when a specific URL needs deeper reading."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Public HTTP(S) URL to read."},
            "no_cache": {"type": "boolean", "description": "Fetch fresh content when possible.", "default": False},
        },
        "required": ["url"],
    }
    repeatable = True

    def execute(self, **kwargs) -> str:
        return read_url(kwargs["url"], no_cache=bool(kwargs.get("no_cache", False)))
