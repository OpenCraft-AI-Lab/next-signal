from __future__ import annotations

import json

from typer.testing import CliRunner

import paca.workflows.knowledge_ingest as knowledge_ingest
from paca.interfaces.cli import app

runner = CliRunner()


def test_knowledge_ingest_progress_outputs_clean_jsonl(monkeypatch) -> None:
    """`--progress` => one JSON event line per step transition + a final result line."""

    def fake_ingest_one(value, *, ingest=True, category=None, on_progress=None, locale="en"):
        assert on_progress is not None
        for step in ("fetch", "clean", "persist"):
            on_progress({"step": step, "status": "start"})
            on_progress({"step": step, "status": "done"})
        return {
            "ok": True,
            "source_type": "web",
            "category": "knowledge/ai-ml",
            "markdown_path": "/wiki/x.md",
            "raw_path": None,
            "frontmatter": {},
        }

    monkeypatch.setattr(knowledge_ingest, "ingest_one", fake_ingest_one)

    result = runner.invoke(
        app, ["knowledge", "ingest", "https://example.com", "--progress", "--no-ingest"]
    )

    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    parsed = [json.loads(ln) for ln in lines]  # every stdout line is valid JSON

    assert parsed[-1]["ok"] is True
    assert parsed[-1]["category"] == "knowledge/ai-ml"
    events = parsed[:-1]
    assert len(events) == 6
    assert {"step": "fetch", "status": "start"} in events
    assert {"step": "persist", "status": "done"} in events


def test_knowledge_ingest_without_progress_emits_single_result(monkeypatch) -> None:
    """No `--progress` => no callback, whole stdout is one result JSON; `--category`/`--locale` wired."""
    seen: dict = {}

    def fake_ingest_one(value, *, ingest=True, category=None, on_progress=None, locale="en"):
        seen["category"] = category
        seen["on_progress"] = on_progress
        seen["locale"] = locale
        return {"ok": True, "category": category}

    monkeypatch.setattr(knowledge_ingest, "ingest_one", fake_ingest_one)

    result = runner.invoke(
        app, ["knowledge", "ingest", "https://example.com", "--category", "life", "--locale", "zh"]
    )

    assert result.exit_code == 0, result.output
    assert seen == {"category": "life", "on_progress": None, "locale": "zh"}
    assert json.loads(result.stdout) == {"ok": True, "category": "life"}
