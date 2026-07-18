"""Render and write the brain-driven `## Related` section in a wiki article.

GBrain owns the relatedness graph; the wiki only carries a deterministic view
of it as a marker-fenced block at the bottom of each `.md`. The block holds
Obsidian-style `[[wikilink]]` references so:

  * Obsidian renders them as clickable links and surfaces them in the
    Backlinks panel automatically.
  * `gbrain dream` 's `extract` phase re-reads the same `[[...]]` syntax back
    into GBrain typed edges, so the brain learns about wiki-visible relations
    on the next cycle (the wiki-↔-brain feedback loop).

Hand edits in the article body are never touched: rewrites only replace the
content between the marker comments. If the marker block is absent, the
section is appended at the end. An empty related list erases the block
entirely so a refresh can shrink as well as grow it.
"""

from __future__ import annotations

import re
from pathlib import Path

from paca.core import paths
from paca.integrations.gbrain import gbrain_slug_for_path

_OPEN_MARKER = "<!-- gbrain:related (auto-generated, do not edit) -->"
_CLOSE_MARKER = "<!-- /gbrain:related -->"
_BLOCK_RE = re.compile(
    r"\n*<!-- gbrain:related[^>]*-->.*?<!-- /gbrain:related -->\n*",
    re.DOTALL,
)


def render_related_section(wiki_paths: list[str]) -> str:
    """Build the marker-fenced markdown block for a list of wiki paths.

    Wiki paths are vault-relative, without `.md` suffix, e.g.
    `knowledge/ai-engineering/Some Title/Some Title`. Empty input returns the
    empty string so callers can blanket-pass results from a query that found
    nothing.
    """
    if not wiki_paths:
        return ""
    bullets = "\n".join(f"- [[{path}]]" for path in wiki_paths)
    return (
        f"{_OPEN_MARKER}\n"
        f"## Related\n\n"
        f"{bullets}\n"
        f"{_CLOSE_MARKER}"
    )


def upsert_related_section(text: str, wiki_paths: list[str]) -> str:
    """Replace the existing marker block in `text` with one for `wiki_paths`.

    If no block exists yet, the new section is appended (with a single blank
    line separator). An empty list deletes the block. Pure function — no I/O.
    """
    stripped = _BLOCK_RE.sub("\n\n", text).rstrip()
    block = render_related_section(wiki_paths)
    if not block:
        return stripped + "\n"
    return f"{stripped}\n\n{block}\n"


def write_related_section(md_path: Path, wiki_paths: list[str]) -> None:
    """Apply `upsert_related_section` in place on the wiki .md file."""
    text = md_path.read_text(encoding="utf-8")
    updated = upsert_related_section(text, wiki_paths)
    if updated != text:
        md_path.write_text(updated, encoding="utf-8")


def resolve_slugs_to_wiki_paths(
    slugs: list[str],
    wiki_dir: Path | None = None,
    *,
    slug_index: dict[str, str] | None = None,
) -> list[str]:
    """Map GBrain slugs to vault-relative wiki paths (no `.md` suffix).

    Returns wikilink targets in input order; slugs that don't resolve to any
    current wiki file are silently dropped (the page may live in another
    GBrain source, or have been moved/deleted). The result is the actual
    `.md` path with suffix stripped — per-article layouts keep the duplicated
    `<dir>/<dir>` segment because stock Obsidian's resolver targets the file,
    not the folder (see `_wikilink_for_path`).

    Pass `slug_index` to skip the wiki walk when looking up many slug batches —
    callers driving a refresh loop should build it once via
    `build_slug_index(wiki_dir)` and pass it on every call.
    """
    if slug_index is None:
        slug_index = build_slug_index(wiki_dir or paths.WIKI_DIR)
    return [slug_index[s] for s in slugs if s in slug_index]


def build_slug_index(wiki_dir: Path) -> dict[str, str]:
    """Walk the wiki once, return `{gbrain_slug: vault-relative wikilink target}`."""
    if not wiki_dir.exists():
        return {}
    slug_to_link: dict[str, str] = {}
    for md_file in wiki_dir.rglob("*.md"):
        rel = md_file.relative_to(wiki_dir)
        slug = gbrain_slug_for_path(rel)
        if slug in slug_to_link:
            continue
        slug_to_link[slug] = _wikilink_for_path(rel)
    return slug_to_link


def _wikilink_for_path(rel: Path) -> str:
    """Vault-relative wikilink target — the actual `.md` file minus suffix.

    Stock Obsidian resolves `[[a/b/c]]` to `a/b/c.md`; it does NOT resolve a
    folder path to a folder note without the Folder Notes plugin. So even for
    per-article layouts where the file is `<dir>/<dir>.md`, we keep the full
    duplicated path and let Obsidian's resolver hit the file directly.
    """
    return rel.with_suffix("").as_posix()
