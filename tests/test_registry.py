"""Verify the tool registry assembles cleanly with all in-tree + integration tools."""

from __future__ import annotations

from paca import registry


def test_registry_loads_all_expected_tools() -> None:
    available = set(registry.available())

    # In-tree (gbrain) + workflow-exposed (knowledge_ingest) + knowledge-domain
    # tool package (search_knowledge). next-signal has no generic cloud-API
    # integrations registered — see paca/integrations/__init__.py.
    expected = {
        "gbrain_search",
        "gbrain_get",
        "gbrain_query",
        "gbrain_ingest",
        "knowledge_ingest_workflow",
        "search_knowledge",
    }
    assert expected.issubset(available), f"missing tools: {expected - available}"


def test_resolve_known_tool() -> None:
    fns = registry.resolve_tools(["search_knowledge"])
    # @tool decorator returns an agno Function wrapper, not a plain callable.
    assert getattr(fns[0], "name", None) == "search_knowledge"


def test_resolve_unknown_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        registry.resolve_tools(["does_not_exist"])
