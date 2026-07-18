"""Agent-facing GBrain knowledge tools."""

from __future__ import annotations

from typing import Any

from agno.tools import tool

from paca.integrations.gbrain import (
    gbrain_get as _gbrain_get,
    gbrain_ingest as _gbrain_ingest,
    gbrain_query as _gbrain_query,
    gbrain_search as _gbrain_search,
)


@tool(show_result=False)
def gbrain_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Search saved markdown knowledge through GBrain."""
    return _gbrain_search(query, limit)


@tool(show_result=False)
def gbrain_get(slug: str) -> dict[str, Any]:
    """Read one saved GBrain page by slug."""
    return _gbrain_get(slug)


@tool(show_result=False)
def gbrain_query(question: str) -> dict[str, Any]:
    """Ask GBrain a hybrid search question."""
    return _gbrain_query(question)


@tool(show_result=False)
def gbrain_ingest(path: str, kind: str = "markdown", slug: str | None = None) -> dict[str, Any]:
    """Import a local markdown file or directory into GBrain."""
    return _gbrain_ingest(path, kind, slug)
