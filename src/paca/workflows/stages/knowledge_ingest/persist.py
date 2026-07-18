"""Persist step: build frontmatter, write the wiki file, then ingest into GBrain.

The wiki artifact is durable even when GBrain ingest fails. GBrain is a derived
index; callers get a loud failure so they can retry indexing without losing the
human-readable markdown already written to disk.
"""

from __future__ import annotations

import calendar
import re
import shutil
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

import yaml

from paca.core import paths
from paca.integrations.gbrain import gbrain_ingest, gbrain_query, gbrain_slug_for_path
from paca.workflows.stages.knowledge_ingest.artifact import KnowledgeArtifact, validate_category
from paca.workflows.stages.knowledge_ingest.related_section import (
    resolve_slugs_to_wiki_paths,
    write_related_section,
)
from paca.workflows.stages.knowledge_ingest.taxonomy import load_taxonomy


def persist(artifact: KnowledgeArtifact, *, ingest: bool = True) -> KnowledgeArtifact:
    """Build frontmatter, write the wiki markdown file, then ingest into GBrain."""
    if artifact.artifact_edit is None:
        raise RuntimeError("persist step requires artifact_edit to be populated")
    artifact.category = validate_category(artifact.category)
    artifact_edit = artifact.artifact_edit

    body = _append_summary_section(artifact.markdown, str(artifact_edit.get("summary") or "").strip())
    artifact_slug = _artifact_slug(artifact.title, artifact.source_type, artifact.digest)
    category_dir = paths.WIKI_DIR / artifact.category
    # Title-derived slugs can collide across DIFFERENT sources (same title,
    # different article). Re-ingesting the SAME source must keep overwriting
    # in place (idempotent update), so only foreign collisions get a suffix.
    existing = _colliding_file(category_dir, artifact_slug)
    if existing is not None and not _same_source(existing, artifact):
        artifact_slug = f"{artifact_slug}-{artifact.digest[:8]}"
    if artifact.assets_dir is not None:
        # Per-article subfolder so the markdown + co-located `images/` ship as
        # one self-contained unit (Obsidian / future moves stay simple).
        article_dir = category_dir / artifact_slug
        clean_path = article_dir / f"{artifact_slug}.md"
    else:
        clean_path = category_dir / f"{artifact_slug}.md"
    gbrain_slug = _gbrain_slug(clean_path)
    frontmatter = _build_frontmatter(artifact, artifact_edit)

    clean_path.parent.mkdir(parents=True, exist_ok=True)
    if artifact.assets_dir is not None and artifact.assets_dir.is_dir():
        shutil.copytree(artifact.assets_dir, clean_path.parent / "images", dirs_exist_ok=True)
    clean_path.write_text(_render(frontmatter, body), encoding="utf-8")
    artifact.markdown = body
    artifact.clean_path = clean_path
    artifact.frontmatter = frontmatter

    if ingest:
        artifact.ingest_result = gbrain_ingest(str(clean_path), slug=gbrain_slug)
        if not artifact.ingest_result.get("ok"):
            raise RuntimeError(
                artifact.ingest_result.get("stderr")
                or artifact.ingest_result.get("error")
                or f"gbrain ingest failed: {clean_path}"
            )
        _write_related_section_for(artifact, clean_path, exclude_slug=gbrain_slug)
    return artifact


def _write_related_section_for(
    artifact: KnowledgeArtifact, clean_path, *, exclude_slug: str
) -> None:
    """Query GBrain for related pages and write the `## Related` block.

    Runs only after a successful gbrain_ingest so the article itself is
    indexed and may show up in its own query — exclude_slug filters it out.
    Best-effort: a query failure logs but never overrides the ingest success.
    """
    query_text = _related_query_text(artifact)
    slugs = related_slugs(query_text, exclude={exclude_slug})
    wiki_paths = resolve_slugs_to_wiki_paths(slugs)
    write_related_section(clean_path, wiki_paths)


def _related_query_text(artifact: KnowledgeArtifact) -> str:
    """Form the GBrain hybrid-query input from the artifact's title + summary."""
    edit = artifact.artifact_edit or {}
    parts = [artifact.title or "", str(edit.get("summary") or "")]
    return "\n".join(p.strip() for p in parts if p.strip())


def _colliding_file(category_dir, slug):
    """Return an existing wiki file that ``slug`` would collide with, if any.

    Both layouts are checked: flat ``<slug>.md`` and per-article
    ``<slug>/<slug>.md`` fold to the same GBrain slug, so a cross-layout
    collision still replaces the other article's index entry.
    """
    for candidate in (category_dir / f"{slug}.md", category_dir / slug / f"{slug}.md"):
        if candidate.is_file():
            return candidate
    return None


def _same_source(existing_path, artifact: KnowledgeArtifact) -> bool:
    """True when the existing wiki file was ingested from the same source."""
    try:
        front = yaml.safe_load(existing_path.read_text(encoding="utf-8").split("---", 2)[1]) or {}
    except Exception:  # noqa: BLE001 — unreadable/foreign file: never claim it
        return False
    if front.get("digest"):
        return str(front["digest"]) == artifact.digest
    # Legacy files predate the frontmatter digest: fall back to source identity.
    source_url = artifact.value if urlparse(artifact.value).scheme in {"http", "https"} else None
    if source_url is not None:
        return front.get("source_url") == source_url
    return artifact.digest in str(front.get("raw_path") or "")


def _build_frontmatter(
    artifact: KnowledgeArtifact, artifact_edit: dict[str, Any]
) -> dict[str, Any]:
    source_url = artifact.value if urlparse(artifact.value).scheme in {"http", "https"} else None
    captured_at = artifact.metadata.get("captured_at") or artifact.created_at
    taxonomy = load_taxonomy()
    freshness = _resolve_freshness(artifact, taxonomy)
    return {
        "title": artifact.title or f"{artifact.source_type}-{artifact.digest}",
        "source_type": artifact.source_type,
        "source_url": source_url,
        "digest": artifact.digest,
        "raw_path": str(artifact.raw_path) if artifact.raw_path else None,
        "created_at": artifact.created_at,
        "captured_at": captured_at,
        "summary": artifact_edit["summary"],
        "tags": artifact_edit["tags"],
        "freshness": freshness,
        "review_by": _review_by(freshness, captured_at, taxonomy),
        "status": "clean",
        **{k: v for k, v in artifact.metadata.items() if _keep_metadata(k, v)},
    }


def _resolve_freshness(artifact: KnowledgeArtifact, taxonomy: dict[str, Any]) -> str:
    """Use the editor's freshness tier; fall back to the category then global default."""
    tiers = taxonomy["freshness"]["tiers"]
    raw = (artifact.artifact_edit or {}).get("freshness")
    if isinstance(raw, str) and raw.strip().lower() in tiers:
        return raw.strip().lower()
    for entry in taxonomy["categories"]:
        if entry["path"] == artifact.category:
            return str(entry["default_freshness"])
    return str(taxonomy["freshness"]["default"])


def _review_by(freshness: str, captured_at: str, taxonomy: dict[str, Any]) -> str | None:
    """Derive a review_by date from the freshness tier and the capture date."""
    months = taxonomy["freshness"]["tiers"][freshness]["review_after_months"]
    if months is None:
        return None
    return _add_months(date.fromisoformat(str(captured_at)[:10]), int(months)).isoformat()


def _add_months(start: date, months: int) -> date:
    index = start.month - 1 + months
    year = start.year + index // 12
    month = index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _render(frontmatter: dict[str, Any], markdown: str) -> str:
    """Render a clean knowledge artifact: YAML frontmatter block + markdown body."""
    yaml_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{yaml_text}\n---\n\n{markdown.strip()}\n"


def _append_summary_section(markdown: str, summary: str) -> str:
    if not summary or re.search(r"(?m)^##\s+总结\s*$", markdown):
        return markdown
    return f"{markdown.rstrip()}\n\n## 总结\n\n{summary}"


def _artifact_slug(title: str, source_type: str, digest: str) -> str:
    slug = _filename_from_title(title)
    if slug:
        return slug
    return f"{datetime.now(UTC).strftime('%Y%m%d')}-{source_type}-{digest}"


def _gbrain_slug(clean_path) -> str:
    return gbrain_slug_for_path(clean_path.relative_to(paths.WIKI_DIR))


def _filename_from_title(title: str) -> str:
    value = re.sub(r"[/:：\\\0]+", "-", title).strip()
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .")[:120].strip(" .")


_RELATED_LIMIT = 8
_RELATED_QUERY_FETCH = 20  # over-fetch so dedup + self-exclusion still leaves enough


def related_slugs(query_text: str, *, exclude: set[str]) -> list[str]:
    """Run a single GBrain hybrid query and return up to _RELATED_LIMIT page slugs.

    Failure is non-fatal — relatedness is best-effort metadata and should never
    take down a successful ingest.
    """
    if not query_text.strip():
        return []
    slugs: list[str] = []
    try:
        result = gbrain_query(query_text, limit=_RELATED_QUERY_FETCH)
        if result.get("ok") and result.get("stdout"):
            for line in str(result["stdout"]).splitlines():
                match = re.match(r"^\[[0-9.]+\]\s+(\S+)\s+--\s+", line.strip())
                if not match:
                    continue
                slug = match.group(1)
                if slug not in exclude and slug not in slugs:
                    slugs.append(slug)
                    if len(slugs) >= _RELATED_LIMIT:
                        break
    except Exception:  # noqa: BLE001 — related lookups are best-effort
        return []
    return slugs


def _keep_metadata(key: str, value: Any) -> bool:
    if key.startswith("_") or key in {"corrected_transcript", "correction_tags"}:
        return False
    return value not in (None, "", [])
