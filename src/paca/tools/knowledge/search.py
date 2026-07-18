"""Agent-facing knowledge search tool."""

from __future__ import annotations

import json
from typing import Any

from agno.tools import tool

from paca.integrations._helpers import truncate
from paca.integrations.gbrain import gbrain_query, gbrain_search


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _result_from_mapping(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or item.get("name") or item.get("slug") or "").strip()
    path = str(item.get("path") or item.get("file") or item.get("url") or "").strip()
    snippet = str(item.get("snippet") or item.get("content") or item.get("text") or "").strip()
    return {
        "title": title or path.rsplit("/", 1)[-1],
        "path": path,
        "snippet": truncate(snippet, 800),
        "score": _coerce_score(item.get("score") or item.get("rank")),
    }


def _parse_search_stdout(stdout: str) -> list[dict[str, Any]]:
    text = stdout.strip()
    if not text or text.lower().startswith("no results"):
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        rows = parsed.get("results") or parsed.get("items") or parsed.get("data") or []
        return [_result_from_mapping(row) for row in rows if isinstance(row, dict)]
    if isinstance(parsed, list):
        return [_result_from_mapping(row) for row in parsed if isinstance(row, dict)]

    results: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                results.append(_result_from_mapping(current))
                current = {}
            continue
        lower = stripped.lower()
        if lower.startswith(("title:", "path:", "snippet:", "score:")):
            key, value = stripped.split(":", 1)
            current[key.lower()] = value.strip()
        elif not current.get("title"):
            current["title"] = stripped.lstrip("-*0123456789. ")
        else:
            current["snippet"] = f"{current.get('snippet', '')} {stripped}".strip()
    if current:
        results.append(_result_from_mapping(current))
    return results


@tool(show_result=False)
def search_knowledge(query: str, topic: str | None = None) -> list[dict[str, Any]]:
    """Search saved wiki knowledge through GBrain."""
    q = f"{topic} {query}".strip() if topic else query
    response = gbrain_search(q, limit=8)
    if not response.get("ok"):
        raise RuntimeError(response.get("error") or response.get("stderr") or "gbrain search failed")
    return _parse_search_stdout(str(response.get("stdout", "")))


def query_knowledge(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Hybrid (vector + keyword + query-expansion) knowledge recall.

    Plain helper, not an agent tool: discovery gather feeds it conceptual goal
    phrases that pure keyword ``search`` misses entirely. Agents wanting hybrid
    recall already have the ``gbrain_query`` tool.
    """
    response = gbrain_query(query, limit=limit)
    if not response.get("ok"):
        raise RuntimeError(response.get("error") or response.get("stderr") or "gbrain query failed")
    return _parse_search_stdout(str(response.get("stdout", "")))
