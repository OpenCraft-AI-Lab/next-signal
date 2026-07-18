"""Tests for the marker-fenced `## Related` block + slug resolver."""

from __future__ import annotations

from pathlib import Path

from paca.workflows.stages.knowledge_ingest.related_section import (
    render_related_section,
    resolve_slugs_to_wiki_paths,
    upsert_related_section,
    write_related_section,
)


def test_render_with_paths_uses_explicit_wikilinks() -> None:
    block = render_related_section([
        "knowledge/ai/foo",
        "tools/wechat/bar/bar",
    ])
    assert "<!-- gbrain:related" in block
    assert "<!-- /gbrain:related -->" in block
    assert "## Related" in block
    assert "- [[knowledge/ai/foo]]" in block
    assert "- [[tools/wechat/bar/bar]]" in block


def test_render_empty_returns_empty_string() -> None:
    assert render_related_section([]) == ""


def test_upsert_appends_block_to_clean_body() -> None:
    body = "# Title\n\nbody text.\n\n## 总结\n\nsummary line.\n"
    out = upsert_related_section(body, ["knowledge/ai/foo", "knowledge/ai/bar"])
    assert "## 总结" in out  # original content untouched
    assert "<!-- gbrain:related" in out
    assert out.count("<!-- gbrain:related") == 1
    assert out.count("<!-- /gbrain:related -->") == 1
    assert "- [[knowledge/ai/foo]]" in out


def test_upsert_replaces_existing_block() -> None:
    body = (
        "# Title\n\nbody.\n\n"
        "<!-- gbrain:related (auto-generated, do not edit) -->\n"
        "## Related\n\n"
        "- [[knowledge/ai/old-one]]\n"
        "<!-- /gbrain:related -->\n"
    )
    out = upsert_related_section(body, ["knowledge/ai/new-one"])
    assert "old-one" not in out
    assert "[[knowledge/ai/new-one]]" in out
    assert out.count("<!-- gbrain:related") == 1


def test_upsert_with_empty_list_deletes_existing_block() -> None:
    body = (
        "# Title\n\nbody.\n\n"
        "<!-- gbrain:related (auto-generated, do not edit) -->\n"
        "## Related\n\n"
        "- [[knowledge/ai/stale]]\n"
        "<!-- /gbrain:related -->\n"
    )
    out = upsert_related_section(body, [])
    assert "gbrain:related" not in out
    assert "stale" not in out
    assert out.endswith("\n")


def test_write_in_place_is_idempotent(tmp_path: Path) -> None:
    md = tmp_path / "note.md"
    md.write_text("# Title\n\nbody.\n", encoding="utf-8")
    write_related_section(md, ["knowledge/ai/foo"])
    first = md.read_text(encoding="utf-8")
    write_related_section(md, ["knowledge/ai/foo"])
    second = md.read_text(encoding="utf-8")
    assert first == second
    assert first.count("<!-- gbrain:related") == 1


def test_resolve_slugs_drops_unknown(tmp_path: Path) -> None:
    (tmp_path / "knowledge" / "ai").mkdir(parents=True)
    (tmp_path / "knowledge" / "ai" / "Foo.md").write_text("# Foo", encoding="utf-8")

    out = resolve_slugs_to_wiki_paths(
        ["knowledge-ai-foo", "does-not-exist"],
        wiki_dir=tmp_path,
    )
    assert out == ["knowledge/ai/Foo"]


def test_resolve_slugs_per_article_folder_full_path(tmp_path: Path) -> None:
    """Per-article layout still resolves to the actual .md path, not the folder."""
    article = tmp_path / "knowledge" / "ai" / "Mnilax-CLAUDE"
    article.mkdir(parents=True)
    (article / "Mnilax-CLAUDE.md").write_text("# x", encoding="utf-8")

    out = resolve_slugs_to_wiki_paths(
        ["knowledge-ai-mnilax-claude"],
        wiki_dir=tmp_path,
    )
    # Vault-relative path of the actual .md file (suffix stripped). The
    # duplicated stem is intentional — that's what stock Obsidian resolves.
    assert out == ["knowledge/ai/Mnilax-CLAUDE/Mnilax-CLAUDE"]


def test_resolve_preserves_input_order(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B", encoding="utf-8")

    # Order in the GBrain result list is significance order; we must preserve it.
    out = resolve_slugs_to_wiki_paths(["b", "a"], wiki_dir=tmp_path)
    assert out == ["b", "a"]
