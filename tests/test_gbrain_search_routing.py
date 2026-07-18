"""gbrain_search routes CJK queries to hybrid `query`, ASCII stays keyword."""

from __future__ import annotations

from paca.integrations import gbrain


def test_has_cjk_truth_table() -> None:
    assert gbrain._has_cjk("记忆框架")
    assert gbrain._has_cjk("Letta 记忆 framework")  # mixed -> still CJK
    assert not gbrain._has_cjk("Letta memory framework")
    assert not gbrain._has_cjk("RAG vs GraphRAG 2.0")


def test_chinese_query_routes_to_hybrid(monkeypatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(
        gbrain, "_run_gbrain", lambda args, **kw: seen.append(args) or {"ok": True}
    )
    gbrain.gbrain_search("Agent 记忆框架对比", limit=5)
    assert seen[0][0] == "query"


def test_ascii_query_stays_keyword(monkeypatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(
        gbrain, "_run_gbrain", lambda args, **kw: seen.append(args) or {"ok": True}
    )
    gbrain.gbrain_search("Letta memory framework", limit=5)
    assert seen[0][0] == "search"
