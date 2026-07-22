from __future__ import annotations

import json
from pathlib import Path

import pytest

from paca.integrations import gbrain
import paca.workflows.stages.knowledge_ingest.artifact_editor as artifact_editor_mod
import paca.workflows.stages.knowledge_ingest.classify as classify_mod
import paca.workflows.stages.knowledge_ingest.fetch as pipeline_fetch
import paca.workflows.stages.knowledge_ingest.persist as persist_mod
from paca.core import paths
from paca.workflows.stages.knowledge_ingest import KnowledgeArtifact
from paca.workflows import knowledge_ingest


@pytest.fixture
def wiki_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("PACA_WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("PACA_WIKI_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setattr(paths, "AGENT_TMP_DIR", tmp_path / "agent-tmp")
    monkeypatch.setattr(knowledge_ingest, "_MANIFEST", tmp_path / "knowledge_ingest_manifest.json")
    # persist queries GBrain for the Related section after a successful ingest
    # — stub both the query and the writer so the workflow tests don't depend
    # on a real gbrain binary or a real wiki to scan.
    monkeypatch.setattr(persist_mod, "gbrain_query", lambda q, limit=None: {"ok": True, "stdout": ""})
    monkeypatch.setattr(persist_mod, "write_related_section", lambda md_path, paths: None)
    return tmp_path


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


def _stub_bilibili(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline_fetch,
        "extract_bilibili",
        lambda url: {
            "ok": True,
            "html": "<html/>",
            "title": "Vid",
            "markdown": "# Vid\n\n## Transcript\n\nspoken body",
            "transcript": "spoken body",
            "metadata": {"bvid": "BV1", "transcript_source": "whisper"},
        },
    )


def _stub_editor(monkeypatch, *, calls: list | None = None, clean: str | None = None) -> None:
    """Stub both edit-phase agents: knowledge_artifact_editor returns plain markdown
    (echoing the body unless `clean` is given), knowledge_frontmatter returns JSON.
    """
    frontmatter = {
        "title": "Vid",
        "summary": "a dense factual summary.",
        "tags": ["alpha", "beta"],
        "freshness": "evolving",
    }

    class FakeAgent:
        def __init__(self, name: str) -> None:
            self.name = name

        def run(self, agent_input, **kwargs):
            if calls is not None:
                calls.append(str(agent_input))
            if self.name == "knowledge_artifact_editor":
                body = clean if clean is not None else json.loads(agent_input)["markdown"]
                return _FakeResponse(body)
            return _FakeResponse(json.dumps(frontmatter, ensure_ascii=False))

    monkeypatch.setattr(
        artifact_editor_mod, "build_from_name", lambda name, locale=None: FakeAgent(name)
    )


def _stub_classifier(monkeypatch, category: str = "knowledge/ai-ml") -> None:
    class FakeAgent:
        def run(self, agent_input, **kwargs):
            return _FakeResponse(json.dumps({"category": category}, ensure_ascii=False))

    monkeypatch.setattr(classify_mod, "build_from_name", lambda name: FakeAgent())


def test_single_source_workflow_runs_all_steps_and_returns_artifact(wiki_paths, monkeypatch) -> None:
    _stub_bilibili(monkeypatch)
    _stub_editor(monkeypatch)
    _stub_classifier(monkeypatch, "knowledge/ai-ml")
    monkeypatch.setattr(persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": True})

    result = knowledge_ingest.build().run(input="https://www.bilibili.com/video/BV1")

    step_names = [entry.step_name for entry in result.step_results or []]
    assert step_names == ["fetch", "clean", "enrich", "classify", "persist"]
    final = result.step_results[-1].content
    assert isinstance(final, KnowledgeArtifact)
    assert final.source_type == "bilibili"
    assert final.category == "knowledge/ai-ml"
    assert final.artifact_edit is not None and final.artifact_edit["tags"] == ["alpha", "beta"]
    assert final.clean_path is not None and Path(final.clean_path).exists()
    assert final.ingest_result == {"ok": True}


def test_single_source_ingest_records_manifest_so_reindex_skips(wiki_paths, monkeypatch) -> None:
    _stub_bilibili(monkeypatch)
    _stub_editor(monkeypatch)
    _stub_classifier(monkeypatch, "knowledge/ai-ml")
    monkeypatch.setattr(persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": True})

    knowledge_ingest.build().run(input="https://www.bilibili.com/video/BV1")

    # the file is already recorded as synced, so a later wiki re-index re-ingests nothing.
    calls: list[str] = []
    result = knowledge_ingest.reindex_wiki(
        wiki_dir=paths.WIKI_DIR,
        manifest_path=knowledge_ingest._MANIFEST,
        ingest_fn=lambda path, slug: calls.append(slug) or {"ok": True},
    )

    assert result["count"] == 0
    assert calls == []


def test_single_source_ingest_failure_keeps_wiki_artifact(wiki_paths, monkeypatch) -> None:
    _stub_bilibili(monkeypatch)
    _stub_editor(monkeypatch)
    _stub_classifier(monkeypatch, "knowledge/ai-ml")
    monkeypatch.setattr(
        persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": False, "stderr": "offline"}
    )

    with pytest.raises(RuntimeError, match="offline"):
        knowledge_ingest.build().run(input="https://www.bilibili.com/video/BV1")

    written = list(paths.WIKI_DIR.rglob("*.md"))
    assert len(written) == 1


def test_single_source_edit_validation_failure_retries_once(wiki_paths, monkeypatch) -> None:
    _stub_bilibili(monkeypatch)
    monkeypatch.setattr(persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": True})
    calls: list[str] = []
    _stub_editor(monkeypatch, clean="", calls=calls)

    with pytest.raises(RuntimeError):
        knowledge_ingest.build().run(input="https://www.bilibili.com/video/BV1")

    assert len(calls) == 2, calls


def test_workflow_classifies_artifact_into_taxonomy_category(wiki_paths, monkeypatch) -> None:
    _stub_bilibili(monkeypatch)
    _stub_editor(monkeypatch)
    _stub_classifier(monkeypatch, "knowledge/ai-engineering")

    result = knowledge_ingest.ingest_one("https://www.bilibili.com/video/BV1", ingest=False)

    assert result["category"] == "knowledge/ai-engineering"
    assert (paths.WIKI_DIR / "knowledge" / "ai-engineering").is_dir()


def test_workflow_falls_back_to_temp_inbox_on_invalid_classification(
    wiki_paths, monkeypatch
) -> None:
    _stub_bilibili(monkeypatch)
    _stub_editor(monkeypatch)
    _stub_classifier(monkeypatch, "made/up/path")

    result = knowledge_ingest.ingest_one("https://www.bilibili.com/video/BV1", ingest=False)

    assert result["category"] == "temp-inbox"


def test_category_override_sets_category_and_skips_classifier(wiki_paths, monkeypatch) -> None:
    _stub_bilibili(monkeypatch)
    _stub_editor(monkeypatch)

    def _boom(name):
        raise AssertionError("classifier must be skipped when a category is pinned")

    monkeypatch.setattr(classify_mod, "build_from_name", _boom)

    result = knowledge_ingest.ingest_one(
        "https://www.bilibili.com/video/BV1", ingest=False, category="investing/quant"
    )

    assert result["category"] == "investing/quant"
    assert (paths.WIKI_DIR / "investing" / "quant").is_dir()


def test_invalid_category_override_raises_before_fetch(wiki_paths, monkeypatch) -> None:
    fetched: list[str] = []
    monkeypatch.setattr(pipeline_fetch, "extract_bilibili", lambda url: fetched.append(url))

    with pytest.raises(RuntimeError, match="unknown knowledge category"):
        knowledge_ingest.ingest_one(
            "https://www.bilibili.com/video/BV1", ingest=False, category="made/up/path"
        )

    assert fetched == []  # validation fails before any fetch work


def test_progress_callback_emits_start_and_done_per_step(wiki_paths, monkeypatch) -> None:
    _stub_bilibili(monkeypatch)
    _stub_editor(monkeypatch)
    _stub_classifier(monkeypatch, "knowledge/ai-ml")
    monkeypatch.setattr(persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": True})

    events: list[dict] = []
    result = knowledge_ingest.ingest_one(
        "https://www.bilibili.com/video/BV1", ingest=True, on_progress=events.append
    )

    # result shape is unchanged by supplying a callback
    assert result["ok"] is True and result["category"] == "knowledge/ai-ml"

    for step in ("fetch", "clean", "enrich", "classify", "persist"):
        assert {"step": step, "status": "start"} in events
        assert {"step": step, "status": "done"} in events
        assert events.index({"step": step, "status": "start"}) < events.index(
            {"step": step, "status": "done"}
        )


def test_failing_step_emits_error_event_naming_step(wiki_paths, monkeypatch) -> None:
    _stub_bilibili(monkeypatch)
    _stub_editor(monkeypatch)
    _stub_classifier(monkeypatch, "knowledge/ai-ml")
    monkeypatch.setattr(
        persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": False, "stderr": "offline"}
    )

    events: list[dict] = []
    with pytest.raises(RuntimeError):
        knowledge_ingest.ingest_one(
            "https://www.bilibili.com/video/BV1", ingest=True, on_progress=events.append
        )

    errors = [e for e in events if e.get("status") == "error"]
    assert any(e["step"] == "persist" for e in errors)


def test_knowledge_ingest_only_reembeds_changed_files(tmp_path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    first = wiki / "first.md"
    second = wiki / "second.md"
    first.write_text("# First\n", encoding="utf-8")
    second.write_text("# Second\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    calls: list[str] = []

    result = knowledge_ingest.reindex_wiki(
        wiki_dir=wiki,
        manifest_path=manifest,
        ingest_fn=lambda path, slug: calls.append(f"{slug}:{Path(path).name}") or {"ok": True},
    )

    assert result["count"] == 2
    assert calls == ["first:first.md", "second:second.md"]

    calls.clear()
    second.write_text("# Second\n\nchanged\n", encoding="utf-8")
    result = knowledge_ingest.reindex_wiki(
        wiki_dir=wiki,
        manifest_path=manifest,
        ingest_fn=lambda path, slug: calls.append(f"{slug}:{Path(path).name}") or {"ok": True},
    )

    assert result["count"] == 1
    assert calls == ["second:second.md"]


def test_knowledge_ingest_skips_temp_inbox_and_output(tmp_path) -> None:
    """Staging (temp-inbox/) and derived-output (output/) trees are never GBrain-indexed."""
    wiki = tmp_path / "wiki"
    (wiki / "knowledge").mkdir(parents=True)
    (wiki / "temp-inbox").mkdir()
    (wiki / "output").mkdir()
    (wiki / "knowledge" / "kept.md").write_text("# Kept\n", encoding="utf-8")
    (wiki / "temp-inbox" / "draft.md").write_text("# Draft\n", encoding="utf-8")
    (wiki / "output" / "post.md").write_text("# Post\n", encoding="utf-8")
    calls: list[str] = []

    result = knowledge_ingest.reindex_wiki(
        wiki_dir=wiki,
        manifest_path=tmp_path / "manifest.json",
        ingest_fn=lambda _path, slug: calls.append(slug) or {"ok": True},
    )

    assert result["count"] == 1
    assert calls == ["knowledge-kept"]


def test_knowledge_ingest_default_routes_through_gbrain_ingest(tmp_path, monkeypatch) -> None:
    """The default ingest path imports each changed file into GBrain by its slug."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "page.md").write_text("# x\n", encoding="utf-8")
    calls: list[tuple[str, str | None]] = []

    def fake_gbrain(path, slug=None):
        calls.append((path, slug))
        return {"ok": True}

    monkeypatch.setattr(knowledge_ingest, "gbrain_ingest", fake_gbrain)

    knowledge_ingest.reindex_wiki(wiki_dir=wiki, manifest_path=tmp_path / "manifest.json")

    assert len(calls) == 1
    path_arg, slug_arg = calls[0]
    assert path_arg.endswith("page.md")
    assert slug_arg == "page"


def test_knowledge_ingest_uses_relative_slug_for_duplicate_basenames(tmp_path) -> None:
    wiki = tmp_path / "wiki"
    (wiki / "finance").mkdir(parents=True)
    (wiki / "research").mkdir(parents=True)
    (wiki / "finance" / "note.md").write_text("# Finance\n", encoding="utf-8")
    (wiki / "research" / "note.md").write_text("# Research\n", encoding="utf-8")
    calls: list[str] = []

    knowledge_ingest.reindex_wiki(
        wiki_dir=wiki,
        manifest_path=tmp_path / "manifest.json",
        ingest_fn=lambda _path, slug: calls.append(slug) or {"ok": True},
    )

    assert calls == ["finance-note", "research-note"]


def test_refresh_wiki_related_rewrites_marker_block(tmp_path) -> None:
    """refresh_wiki_related queries gbrain per page and (re)writes the marker block."""
    wiki = tmp_path / "wiki"
    (wiki / "knowledge").mkdir(parents=True)
    article = wiki / "knowledge" / "Foo.md"
    article.write_text(
        "---\ntitle: Foo\nsummary: a dense factual summary.\ntags: [a]\n---\n\n"
        "# Foo\n\nbody.\n",
        encoding="utf-8",
    )
    neighbor = wiki / "knowledge" / "Bar.md"
    neighbor.write_text(
        "---\ntitle: Bar\nsummary: another dense summary.\ntags: [b]\n---\n\n"
        "# Bar\n\nbody.\n",
        encoding="utf-8",
    )

    def fake_query(query_text: str, exclude: set[str]) -> list[str]:
        # Each page should find the other one, never itself.
        return [s for s in ("knowledge-foo", "knowledge-bar") if s not in exclude]

    result = knowledge_ingest.refresh_wiki_related(wiki_dir=wiki, query_fn=fake_query)

    assert result["count"] == 2
    foo_text = article.read_text(encoding="utf-8")
    bar_text = neighbor.read_text(encoding="utf-8")
    assert "[[knowledge/Bar]]" in foo_text
    assert "[[knowledge/Foo]]" in bar_text


def test_refresh_wiki_related_skips_files_without_frontmatter(tmp_path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "naked.md").write_text("# No frontmatter\n", encoding="utf-8")

    called: list[str] = []
    result = knowledge_ingest.refresh_wiki_related(
        wiki_dir=wiki,
        query_fn=lambda q, exclude: called.append(q) or [],
    )

    assert called == []  # never queried
    assert result["count"] == 0
    assert result["skipped"] == ["naked.md"]


def test_weekly_sync_runs_reindex_then_refresh(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    (wiki / "knowledge").mkdir(parents=True)
    (wiki / "knowledge" / "page.md").write_text(
        "---\ntitle: Page\nsummary: s.\ntags: [a]\n---\n\nbody\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"

    monkeypatch.setattr(knowledge_ingest, "_default_related_query", lambda t, e: [])

    result = knowledge_ingest.weekly_sync(
        wiki_dir=wiki,
        manifest_path=manifest_path,
        ingest_fn=lambda path, slug: {"ok": True},
    )

    assert result["reindex"]["count"] == 1
    assert result["related_refresh"]["count"] == 1


def test_knowledge_ingest_keeps_non_ascii_slugs_distinct(tmp_path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "视觉原语.md").write_text("# A\n", encoding="utf-8")
    (wiki / "指代断裂.md").write_text("# B\n", encoding="utf-8")
    calls: list[str] = []

    knowledge_ingest.reindex_wiki(
        wiki_dir=wiki,
        manifest_path=tmp_path / "manifest.json",
        ingest_fn=lambda _path, slug: calls.append(slug) or {"ok": True},
    )

    assert len(calls) == 2
    assert calls[0] != calls[1]
    assert all(slug.startswith("page-") for slug in calls)


def test_gbrain_ingest_file_uses_put_and_embed(tmp_path, monkeypatch) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Note\n", encoding="utf-8")
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(args, *, timeout=60, stdin=None):
        calls.append((args, stdin))
        return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(gbrain, "_run_gbrain", fake_run)

    result = gbrain.gbrain_ingest(str(source))

    assert result["ok"] is True
    assert calls == [(["put", "note"], "# Note\n"), (["embed", "note"], None)]


def test_gbrain_ingest_file_reports_embed_failure(tmp_path, monkeypatch) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Note\n", encoding="utf-8")

    def fake_run(args, *, timeout=60, stdin=None):
        if args[0] == "embed":
            return {"ok": False, "stdout": "", "stderr": "missing key", "returncode": 1}
        return {"ok": True, "stdout": "saved", "stderr": "", "returncode": 0}

    monkeypatch.setattr(gbrain, "_run_gbrain", fake_run)

    result = gbrain.gbrain_ingest(str(source))

    assert result["ok"] is False
    assert result["embedding_ok"] is False
    assert "missing key" in result["stderr"]


def test_gbrain_ingest_file_accepts_relative_slug(tmp_path, monkeypatch) -> None:
    source = tmp_path / "finance" / "note.md"
    source.parent.mkdir()
    source.write_text("# Note\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(args, *, timeout=60, stdin=None):
        calls.append(args)
        return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(gbrain, "_run_gbrain", fake_run)

    result = gbrain.gbrain_ingest(str(source), slug="finance/note")

    assert result["ok"] is True
    assert result["slug"] == "finance-note"
    assert calls == [["put", "finance-note"], ["embed", "finance-note"]]
