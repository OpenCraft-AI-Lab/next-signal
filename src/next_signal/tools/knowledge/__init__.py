"""Knowledge-domain agent-facing tools."""

from __future__ import annotations


def register(registry) -> None:
    from next_signal.tools.knowledge import search

    registry.register("search_knowledge", search.search_knowledge)
