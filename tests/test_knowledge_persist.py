from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import paca.workflows.stages.knowledge_ingest.persist as persist_mod
from paca.core import paths
from paca.workflows.stages.knowledge_ingest import KnowledgeArtifact
from paca.workflows.stages.knowledge_ingest.persist import _artifact_slug, persist, related_slugs


@pytest.fixture(autouse=True)
def _wiki_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PACA_WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setattr(persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": True})
    # Related-section step needs both a quiet gbrain_query and an in-place
    # writer that no-ops in tests by default — specific tests can restore
    # either to assert on real behavior.
    monkeypatch.setattr(persist_mod, "gbrain_query", lambda q, limit=None: {"ok": True, "stdout": ""})
    monkeypatch.setattr(persist_mod, "write_related_section", lambda md_path, wiki_paths: None)
    # Tag-label translation is a best-effort DB + LLM side effect; stub it so
    # persist unit tests stay offline (a zh ingest would otherwise call OMLX).
    monkeypatch.setattr(persist_mod, "ensure_tag_labels", lambda tags, locale: None)
    return tmp_path


def _ready(
    *,
    source_type: str = "web",
    title: str = "Note Title",
    category: str = "knowledge/sub",
    freshness: str | None = "stable",
    metadata: dict | None = None,
) -> KnowledgeArtifact:
    return KnowledgeArtifact(
        value="https://example.com/x",
        source_type=source_type,
        digest="abc123",
        created_at="2026-05-15T00:00:00+00:00",
        category=category,
        title=title,
        markdown="# Note Title\n\nbody paragraph.",
        metadata=metadata or {},
        artifact_edit={
            "summary": "a dense factual summary.",
            "tags": ["alpha", "beta"],
            "freshness": freshness,
        },
    )


def _frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


def test_persist_raises_without_artifact_edit() -> None:
    a = _ready()
    a.artifact_edit = None
    with pytest.raises(RuntimeError, match="artifact_edit"):
        persist(a)


def test_persist_writes_wiki_file_and_frontmatter() -> None:
    result = persist(_ready())

    assert result.clean_path is not None and result.clean_path.exists()
    assert result.clean_path.name == "Note Title.md"
    fm = _frontmatter(result.clean_path)
    assert fm["title"] == "Note Title"
    assert fm["source_type"] == "web"
    assert fm["tags"] == ["alpha", "beta"]
    assert fm["summary"] == "a dense factual summary."
    assert fm["status"] == "clean"


def test_persist_writes_locale_and_source_title() -> None:
    artifact = _ready()
    artifact.source_title = "Original Source Title"
    result = persist(artifact, locale="zh")
    fm = _frontmatter(result.clean_path)
    assert fm["locale"] == "zh"
    assert fm["source_title"] == "Original Source Title"


def test_persist_appends_summary_section() -> None:
    # Default locale is English (paca.core.config.DEFAULT_LOCALE = "en").
    result = persist(_ready())
    text = result.clean_path.read_text(encoding="utf-8")
    assert "## Summary\n\na dense factual summary." in text


def test_persist_summary_heading_is_canonical_english() -> None:
    # The stored heading is canonical English regardless of the ingest locale; the
    # dashboard localizes it at render by the artifact's `locale`. This keeps the
    # .md stable across locales and avoids baking the UI language into storage.
    result = persist(_ready(), locale="zh")
    text = result.clean_path.read_text(encoding="utf-8")
    assert "## Summary\n\na dense factual summary." in text
    assert "## 总结" not in text


def test_persist_uses_editor_freshness_tier() -> None:
    result = persist(_ready(freshness="ephemeral"))
    assert _frontmatter(result.clean_path)["freshness"] == "ephemeral"


def test_persist_derives_review_by_from_freshness() -> None:
    # captured_at 2026-05-15 + stable's 24-month window.
    result = persist(_ready(freshness="stable"))
    assert _frontmatter(result.clean_path)["review_by"] == "2028-05-15"


def test_persist_ephemeral_review_by_is_one_month_out() -> None:
    result = persist(_ready(freshness="ephemeral"))
    assert _frontmatter(result.clean_path)["review_by"] == "2026-06-15"


def test_persist_permanent_freshness_has_no_review_by() -> None:
    result = persist(_ready(freshness="permanent"))
    assert _frontmatter(result.clean_path)["review_by"] is None


def test_persist_falls_back_to_category_default_freshness() -> None:
    # knowledge/ai-engineering defaults to evolving in the taxonomy.
    result = persist(_ready(category="knowledge/ai-engineering", freshness=None))
    assert _frontmatter(result.clean_path)["freshness"] == "evolving"


def test_persist_falls_back_to_global_default_freshness() -> None:
    # knowledge/sub is not a taxonomy category, so the global default applies.
    result = persist(_ready(freshness=None))
    assert _frontmatter(result.clean_path)["freshness"] == "stable"


def test_persist_slug_falls_back_when_title_empty() -> None:
    result = persist(_ready(title=""))
    assert result.clean_path is not None
    assert "web-abc123" in result.clean_path.stem


def test_persist_passes_through_source_metadata() -> None:
    result = persist(
        _ready(source_type="wechat", metadata={"account": "Acct", "provider": "opencli"})
    )
    fm = _frontmatter(result.clean_path)
    assert fm["account"] == "Acct"
    assert fm["provider"] == "opencli"


def test_persist_ingests_when_enabled(monkeypatch) -> None:
    calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        persist_mod,
        "gbrain_ingest",
        lambda path, slug=None: calls.append((path, slug)) or {"ok": True, "indexed": 1},
    )
    result = persist(_ready())
    assert result.ingest_result == {"ok": True, "indexed": 1}
    assert calls[0][1] == "knowledge-sub-note-title"


def test_persist_skips_ingest_when_disabled(monkeypatch) -> None:
    def boom(*a, **k):
        raise AssertionError("gbrain_ingest must not be called when ingest=False")

    monkeypatch.setattr(persist_mod, "gbrain_ingest", boom)
    result = persist(_ready(), ingest=False)
    assert result.ingest_result is None
    assert result.clean_path is not None and result.clean_path.exists()


def test_persist_keeps_flat_wiki_file_on_ingest_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": False, "error": "offline"}
    )
    with pytest.raises(RuntimeError, match="offline"):
        persist(_ready())
    assert (paths.WIKI_DIR / "knowledge" / "sub" / "Note Title.md").exists()


def test_persist_keeps_per_article_folder_on_ingest_failure(monkeypatch, tmp_path) -> None:
    assets = tmp_path / "src_images"
    assets.mkdir()
    (assets / "img_001.png").write_bytes(b"x")
    monkeypatch.setattr(
        persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": False, "error": "offline"}
    )
    artifact = _ready(source_type="wechat")
    artifact.assets_dir = assets
    with pytest.raises(RuntimeError, match="offline"):
        persist(artifact)
    article_dir = paths.WIKI_DIR / "knowledge" / "sub" / "Note Title"
    assert (article_dir / "Note Title.md").exists()
    assert (article_dir / "images" / "img_001.png").exists()


def test_persist_same_title_different_source_gets_digest_suffix() -> None:
    first = persist(_ready())
    second = _ready()
    second.value = "https://example.com/other-article"
    second.digest = "def456"
    second.markdown = "# Note Title\n\ndifferent body."
    result = persist(second)

    assert result.clean_path != first.clean_path
    assert result.clean_path.name == "Note Title-def456.md"
    # The first article survives untouched.
    assert first.clean_path.exists()
    assert "body paragraph." in first.clean_path.read_text(encoding="utf-8")
    assert _frontmatter(result.clean_path)["digest"] == "def456"


def test_persist_same_source_reingest_overwrites_in_place() -> None:
    first = persist(_ready())
    updated = _ready()
    updated.markdown = "# Note Title\n\nrevised body."
    result = persist(updated)

    assert result.clean_path == first.clean_path
    assert "revised body." in result.clean_path.read_text(encoding="utf-8")
    assert len(list(result.clean_path.parent.glob("*.md"))) == 1


def test_persist_legacy_file_without_digest_matches_on_source_url() -> None:
    # Pre-digest wiki files only carry source_url; same source must still
    # overwrite in place rather than fork a suffixed duplicate.
    legacy = paths.WIKI_DIR / "knowledge" / "sub" / "Note Title.md"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        "---\ntitle: Note Title\nsource_url: https://example.com/x\n---\n\nold body\n",
        encoding="utf-8",
    )
    result = persist(_ready())
    assert result.clean_path == legacy
    assert len(list(legacy.parent.glob("*.md"))) == 1


def test_persist_legacy_file_different_source_url_gets_suffix() -> None:
    # Legacy file from ANOTHER source with the same title must not be replaced.
    legacy = paths.WIKI_DIR / "knowledge" / "sub" / "Note Title.md"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        "---\ntitle: Note Title\nsource_url: https://elsewhere.com/article\n---\n\nold body\n",
        encoding="utf-8",
    )
    result = persist(_ready())
    assert result.clean_path.name == "Note Title-abc123.md"
    assert "old body" in legacy.read_text(encoding="utf-8")


def test_persist_legacy_file_source_matches_on_raw_path_digest() -> None:
    # File-source artifacts have no source_url; legacy identity falls back to
    # the digest embedded in the raw archive path.
    legacy = paths.WIKI_DIR / "knowledge" / "sub" / "Note Title.md"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        "---\ntitle: Note Title\nraw_path: /raw/markdown/abc123/source.md\n---\n\nold body\n",
        encoding="utf-8",
    )
    artifact = _ready()
    artifact.value = "staged-note.md"  # non-URL source
    result = persist(artifact)
    assert result.clean_path == legacy
    assert len(list(legacy.parent.glob("*.md"))) == 1


def test_persist_unparseable_existing_file_treated_as_foreign() -> None:
    # A colliding file we can't attribute (no frontmatter) is never claimed.
    stray = paths.WIKI_DIR / "knowledge" / "sub" / "Note Title.md"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("just some hand-written note\n", encoding="utf-8")
    result = persist(_ready())
    assert result.clean_path.name == "Note Title-abc123.md"
    assert stray.read_text(encoding="utf-8") == "just some hand-written note\n"


def test_persist_cross_layout_title_collision_gets_suffix(tmp_path) -> None:
    # Flat `<slug>.md` and per-article `<slug>/<slug>.md` fold to the same
    # GBrain slug, so a per-article artifact must not shadow a flat one.
    persist(_ready())
    assets = tmp_path / "imgs"
    assets.mkdir()
    (assets / "a.png").write_bytes(b"x")
    other = _ready(source_type="wechat")
    other.value = "https://example.com/other"
    other.digest = "fee1dead9999"
    other.assets_dir = assets
    result = persist(other)

    assert result.clean_path.parent.name == "Note Title-fee1dead"
    assert result.clean_path.name == "Note Title-fee1dead.md"


def test_artifact_slug_uses_title_as_filename() -> None:
    assert _artifact_slug("DeepSeek 视觉原语：指代断裂", "bilibili", "abc123") == "DeepSeek 视觉原语-指代断裂"


def test_artifact_slug_falls_back_to_dated_slug() -> None:
    assert _artifact_slug("", "web", "abc123").endswith("web-abc123")


def test_related_slugs_ignores_no_results(monkeypatch) -> None:
    monkeypatch.setattr(
        persist_mod, "gbrain_query", lambda q, limit=None: {"ok": True, "stdout": "No results."}
    )
    assert related_slugs("omlx is local", exclude=set()) == []


def test_related_slugs_parses_result_lines(monkeypatch) -> None:
    monkeypatch.setattr(
        persist_mod,
        "gbrain_query",
        lambda q, limit=None: {
            "ok": True,
            "stdout": "[0.99] slug -- # Title\n\n## Metadata\n\n- Source: https://example.com",
        },
    )
    assert related_slugs("deepseek visual primitives", exclude=set()) == ["slug"]


def test_related_slugs_excludes_self_and_dedupes(monkeypatch) -> None:
    monkeypatch.setattr(
        persist_mod,
        "gbrain_query",
        lambda q, limit=None: {
            "ok": True,
            "stdout": (
                "[0.99] current-slug -- # Current\n"
                "[0.88] other-slug -- # Other\n"
                "[0.77] other-slug -- # Other (duplicate)\n"
                "[0.66] third-slug -- # Third"
            ),
        },
    )
    assert related_slugs(
        "deepseek", exclude={"current-slug"}
    ) == ["other-slug", "third-slug"]


def test_related_slugs_empty_query_text() -> None:
    assert related_slugs("   ", exclude=set()) == []
