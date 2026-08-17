from __future__ import annotations

import json
from pathlib import Path

import pytest

from next_signal.tools.knowledge import search as search_mod


def _brain(home: Path, **config: object) -> Path:
    """An initialised GBrain home, so the search guard lets the call through."""
    (home / ".gbrain").mkdir(parents=True, exist_ok=True)
    (home / ".gbrain" / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return home


def test_search_knowledge_normalizes_gbrain_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GBRAIN_HOME", str(_brain(tmp_path, embedding_model="openai:x")))
    monkeypatch.setattr(
        search_mod,
        "gbrain_search",
        lambda query, limit=8: {
            "ok": True,
            "stdout": """
{
  "results": [
    {
      "title": "NVDA Q4",
      "path": "~/Projects/digitalpaca-wiki/finance/nvda.md",
      "snippet": "Q4 data center highlights",
      "score": 0.91
    }
  ]
}
""",
        },
    )

    assert search_mod.search_knowledge.entrypoint("Q4 NVDA highlights") == [
        {
            "title": "NVDA Q4",
            "path": "~/Projects/digitalpaca-wiki/finance/nvda.md",
            "snippet": "Q4 data center highlights",
            "score": 0.91,
        }
    ]


def test_search_refuses_when_brain_is_absent(tmp_path: Path, monkeypatch) -> None:
    """An empty result would be indistinguishable from "nothing on this topic"."""
    monkeypatch.setenv("GBRAIN_HOME", str(tmp_path))

    with pytest.raises(RuntimeError, match="not been initialised"):
        search_mod.search_knowledge.entrypoint("anything")


def test_query_knowledge_refuses_when_brain_is_absent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GBRAIN_HOME", str(tmp_path))

    with pytest.raises(RuntimeError, match="not been initialised"):
        search_mod.query_knowledge("anything")


def test_search_proceeds_when_state_is_indeterminate(tmp_path: Path, monkeypatch) -> None:
    """Only a definite "not initialised" blocks; an unreadable config does not."""
    (tmp_path / ".gbrain").mkdir()
    (tmp_path / ".gbrain" / "config.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("GBRAIN_HOME", str(tmp_path))
    monkeypatch.setattr(
        search_mod, "gbrain_search", lambda query, limit=8: {"ok": True, "stdout": "No results."}
    )

    assert search_mod.search_knowledge.entrypoint("anything") == []
