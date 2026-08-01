"""Web and deep-research search tool backed by Exa."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool
from src.security.scanner import with_security_warnings
from src.tools._exa_client import ExaConfigError, exa_post, exa_secret_configured

_SEARCH_TYPES = {"instant", "fast", "auto", "deep-lite", "deep", "deep-reasoning"}
_CATEGORIES = {"company", "publication", "news", "personal site", "financial report", "people"}


def _string_list(value: Any) -> list[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return None


class WebSearchTool(BaseTool):
    """Search and deep research via Exa."""

    name = "web_search"

    @classmethod
    def check_available(cls) -> bool:
        return exa_secret_configured()

    description = (
        "Search the web with Exa AI. Supports fast lookup and deep research "
        "using search types instant, fast, auto, deep-lite, deep, and "
        "deep-reasoning. Returns titles, URLs, publication dates, highlights, "
        "summaries, and synthesized output when requested."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search or research query."},
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default 5, max 20).",
                "default": 5,
            },
            "search_type": {
                "type": "string",
                "enum": sorted(_SEARCH_TYPES),
                "description": "Exa search mode. Use deep or deep-reasoning for market research.",
                "default": "auto",
            },
            "category": {
                "type": "string",
                "enum": sorted(_CATEGORIES),
                "description": "Optional Exa category hint, such as news, company, publication, or financial report.",
            },
            "include_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional domains or domain paths to include.",
            },
            "exclude_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional domains or domain paths to exclude.",
            },
            "start_published_date": {
                "type": "string",
                "description": "Only return links published after this ISO-8601 date/time.",
            },
            "end_published_date": {
                "type": "string",
                "description": "Only return links published before this ISO-8601 date/time.",
            },
            "synthesize": {
                "type": "boolean",
                "description": "Ask Exa to synthesize a grounded research answer.",
                "default": False,
            },
        },
        "required": ["query"],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        raw_query = kwargs.get("query")
        if not isinstance(raw_query, str) or not raw_query.strip():
            return json.dumps(
                {"status": "error", "tool": self.name, "error": "query is mandatory"},
                ensure_ascii=False,
            )

        try:
            max_results = min(max(1, int(kwargs.get("max_results") or 5)), 20)
        except (TypeError, ValueError, OverflowError):
            return json.dumps(
                {"status": "error", "tool": self.name, "error": "max_results must be an integer"},
                ensure_ascii=False,
            )

        search_type = str(kwargs.get("search_type") or "auto").strip()
        if search_type not in _SEARCH_TYPES:
            return json.dumps(
                {
                    "status": "error",
                    "tool": self.name,
                    "error": f"search_type must be one of {sorted(_SEARCH_TYPES)}",
                },
                ensure_ascii=False,
            )

        body: dict[str, Any] = {
            "query": raw_query.strip(),
            "numResults": max_results,
            "type": search_type,
            "contents": {
                "highlights": True,
                "summary": {"query": raw_query.strip()},
            },
        }
        category = str(kwargs.get("category") or "").strip()
        if category:
            body["category"] = category
        for local_key, exa_key in (
            ("include_domains", "includeDomains"),
            ("exclude_domains", "excludeDomains"),
        ):
            values = _string_list(kwargs.get(local_key))
            if values:
                body[exa_key] = values
        if kwargs.get("start_published_date"):
            body["startPublishedDate"] = str(kwargs["start_published_date"])
        if kwargs.get("end_published_date"):
            body["endPublishedDate"] = str(kwargs["end_published_date"])
        if bool(kwargs.get("synthesize")) or search_type in {"deep", "deep-reasoning"}:
            body["outputSchema"] = {"type": "text"}
            body["systemPrompt"] = (
                "Produce concise English market research with explicit citations. "
                "Prefer primary sources, filings, official docs, and reputable financial media."
            )

        try:
            data = exa_post("/search", body, timeout=60 if search_type.startswith("deep") else 30)
        except ExaConfigError as exc:
            return json.dumps({"status": "error", "tool": self.name, "error": str(exc)}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error", "tool": self.name, "error": str(exc)}, ensure_ascii=False)

        results = []
        for item in data.get("results") or []:
            highlights = item.get("highlights") or []
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "published_date": item.get("publishedDate"),
                "author": item.get("author"),
                "snippet": highlights[0] if highlights else item.get("summary") or "",
                "highlights": highlights[:3],
                "summary": item.get("summary"),
                "source": "exa",
            })

        payload: dict[str, Any] = {
            "status": "ok",
            "tool": self.name,
            "provider": "exa",
            "query": raw_query.strip(),
            "search_type": search_type,
            "results": results,
            "request_id": data.get("requestId"),
        }
        if data.get("output"):
            payload["output"] = data["output"]
        if data.get("costDollars"):
            payload["cost_dollars"] = data["costDollars"]

        payload = with_security_warnings(
            payload,
            fields=("results.*.title", "results.*.snippet", "results.*.summary", "output.content"),
        )
        return json.dumps(payload, ensure_ascii=False)
