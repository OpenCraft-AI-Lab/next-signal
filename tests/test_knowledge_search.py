from __future__ import annotations

from paca.tools.knowledge import search as search_mod


def test_search_knowledge_normalizes_gbrain_json(monkeypatch) -> None:
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
      "path": "/Users/digital-paca/Projects/digitalpaca-wiki/finance/nvda.md",
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
            "path": "/Users/digital-paca/Projects/digitalpaca-wiki/finance/nvda.md",
            "snippet": "Q4 data center highlights",
            "score": 0.91,
        }
    ]
