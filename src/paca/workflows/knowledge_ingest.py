"""Knowledge ingest + sync workflows.

Single-source ingest turns a URL or staged local file into a wiki markdown
artifact and optionally indexes it in GBrain. The weekly sync workflow does
two things in order: (1) re-ingest wiki files whose digest has changed, and
(2) refresh the brain-driven `## Related` block in every wiki file by
re-querying GBrain for that article's neighbors.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

import yaml
from agno.workflow import Step, Workflow
from agno.workflow.types import OnError, StepInput, StepOutput

from paca.core import paths
from paca.core.config import DEFAULT_LOCALE
from paca.integrations.gbrain import gbrain_ingest, gbrain_slug_for_path
from paca.workflows.stages.knowledge_ingest import KnowledgeArtifact
from paca.workflows.stages.knowledge_ingest.artifact_editor import clean_body, write_frontmatter
from paca.workflows.stages.knowledge_ingest.classify import classify_category
from paca.workflows.stages.knowledge_ingest.fetch import fetch
from paca.workflows.stages.knowledge_ingest.persist import persist, related_slugs
from paca.workflows.stages.knowledge_ingest.related_section import (
    build_slug_index,
    resolve_slugs_to_wiki_paths,
    write_related_section,
)
from paca.workflows.stages.knowledge_ingest.taxonomy import category_paths, load_taxonomy

_MANIFEST = paths.STATE_ROOT / "knowledge_ingest_manifest.json"
_UNINDEXED_DIRS = {"temp-inbox", "output"}
WORKFLOW_ID = "knowledge_ingest"


def _markdown_files(root: Path) -> list[Path]:
    """Wiki markdown files, excluding the staging and derived-output trees."""
    if not root.exists():
        raise RuntimeError(f"wiki directory missing: {root}")
    return sorted(
        p
        for p in root.rglob("*.md")
        if p.is_file() and p.relative_to(root).parts[0] not in _UNINDEXED_DIRS
    )


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(path: Path = _MANIFEST) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid knowledge ingest manifest: {path}")
    return {str(k): str(v) for k, v in data.items()}


def _save_manifest(data: dict[str, str], path: Path = _MANIFEST) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _mark_ingested(artifact: KnowledgeArtifact) -> None:
    """Record a freshly ingested wiki file so a later wiki re-index skips it."""
    if artifact.clean_path is None:
        return
    rel = artifact.clean_path.relative_to(paths.WIKI_DIR).as_posix()
    manifest = _load_manifest(_MANIFEST)
    manifest[rel] = _digest(artifact.clean_path)
    _save_manifest(manifest, _MANIFEST)


def changed_files(wiki_dir: Path | None = None, manifest_path: Path = _MANIFEST) -> list[Path]:
    """Return markdown files whose current digest is absent from the last GBrain ingest."""
    wiki_dir = wiki_dir or paths.WIKI_DIR
    manifest = _load_manifest(manifest_path)
    changed: list[Path] = []
    for path in _markdown_files(wiki_dir):
        rel = path.relative_to(wiki_dir).as_posix()
        digest = _digest(path)
        if manifest.get(rel) != digest:
            changed.append(path)
    return changed


def reindex_wiki(
    wiki_dir: Path | None = None,
    manifest_path: Path = _MANIFEST,
    ingest_fn: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Re-ingest changed wiki markdown files into GBrain.

    Each changed file is imported by its wiki-relative slug, so a file ingests
    to the same GBrain page identity it had on the previous run.
    """
    wiki_dir = wiki_dir or paths.WIKI_DIR
    ingest = ingest_fn or _default_ingest
    manifest = _load_manifest(manifest_path)
    new_manifest: dict[str, str] = {}
    ingested: list[str] = []

    for path in _markdown_files(wiki_dir):
        rel = path.relative_to(wiki_dir).as_posix()
        digest = _digest(path)
        new_manifest[rel] = digest
        if manifest.get(rel) == digest:
            continue
        slug = gbrain_slug_for_path(rel)
        result = ingest(str(path), slug)
        if not result.get("ok"):
            raise RuntimeError(result.get("stderr") or result.get("error") or f"gbrain ingest failed: {path}")
        ingested.append(str(path))

    _save_manifest(new_manifest, manifest_path)
    return {"ok": True, "wiki_dir": str(wiki_dir), "ingested": ingested, "count": len(ingested)}


def refresh_wiki_related(
    wiki_dir: Path | None = None,
    *,
    query_fn: Callable[[str, set[str]], list[str]] | None = None,
    resolve_fn: Callable[[list[str]], list[str]] | None = None,
    writer_fn: Callable[[Path, list[str]], None] | None = None,
) -> dict[str, Any]:
    """Rebuild the marker-fenced `## Related` block in every wiki .md file.

    For each article: re-query GBrain with that article's `title + summary`
    pulled from its frontmatter, resolve the returned slugs back to wiki
    paths, and rewrite the marker block in place. The block carries
    `[[wikilink]]` references that Obsidian renders and `gbrain extract`
    re-ingests as typed edges. Articles without a parseable frontmatter or
    with empty title/summary are skipped (not refreshed but not erased).
    """
    wiki_dir = wiki_dir or paths.WIKI_DIR
    query = query_fn or _default_related_query
    if resolve_fn is None:
        # Walk the wiki tree once up front so the per-article resolve becomes
        # an O(1) dict lookup instead of an O(N) rglob per file.
        slug_index = build_slug_index(wiki_dir)
        resolve = lambda slugs: resolve_slugs_to_wiki_paths(slugs, slug_index=slug_index)  # noqa: E731
    else:
        resolve = resolve_fn
    write = writer_fn or write_related_section

    refreshed: list[str] = []
    skipped: list[str] = []
    for md_path in _markdown_files(wiki_dir):
        rel = md_path.relative_to(wiki_dir).as_posix()
        text = md_path.read_text(encoding="utf-8")
        frontmatter = _read_frontmatter(text)
        if not frontmatter:
            skipped.append(rel)
            continue
        query_text = _related_query_text_from_frontmatter(frontmatter)
        if not query_text:
            skipped.append(rel)
            continue
        own_slug = gbrain_slug_for_path(rel)
        slugs = query(query_text, {own_slug})
        wiki_paths = resolve(slugs)
        write(md_path, wiki_paths)
        refreshed.append(rel)
    return {
        "ok": True,
        "wiki_dir": str(wiki_dir),
        "refreshed": refreshed,
        "skipped": skipped,
        "count": len(refreshed),
    }


def weekly_sync(
    wiki_dir: Path | None = None,
    manifest_path: Path = _MANIFEST,
    ingest_fn: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Weekly sync: re-embed changed files, then refresh every Related block.

    The two phases run unconditionally — even when no file changed, the
    Related refresh still picks up new neighbors that appeared elsewhere in
    the brain since the last cycle.
    """
    wiki_dir = wiki_dir or paths.WIKI_DIR
    reindex_result = reindex_wiki(
        wiki_dir=wiki_dir, manifest_path=manifest_path, ingest_fn=ingest_fn
    )
    refresh_result = refresh_wiki_related(wiki_dir=wiki_dir)
    return {
        "ok": True,
        "reindex": reindex_result,
        "related_refresh": refresh_result,
    }


def run(
    wiki_dir: Path | None = None,
    manifest_path: Path = _MANIFEST,
    ingest_fn: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Scheduled weekly entry point — kept for backwards compat."""
    return weekly_sync(wiki_dir=wiki_dir, manifest_path=manifest_path, ingest_fn=ingest_fn)


def _default_related_query(query_text: str, exclude: set[str]) -> list[str]:
    return related_slugs(query_text, exclude=exclude)


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _read_frontmatter(text: str) -> dict[str, Any] | None:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _related_query_text_from_frontmatter(frontmatter: dict[str, Any]) -> str:
    parts = [str(frontmatter.get("title") or ""), str(frontmatter.get("summary") or "")]
    return "\n".join(p.strip() for p in parts if p.strip())


def _default_ingest(path: str, slug: str) -> dict[str, Any]:
    """Import one wiki markdown file into GBrain under its wiki-relative slug."""
    return gbrain_ingest(path, slug=slug)


def _ingest_enabled(inp: StepInput) -> bool:
    data = inp.additional_data or {}
    return bool(data.get("ingest", True))


def _locale(inp: StepInput) -> str:
    data = inp.additional_data or {}
    return str(data.get("locale") or DEFAULT_LOCALE)


def _artifact_from(inp: StepInput) -> KnowledgeArtifact:
    artifact = inp.previous_step_content
    if isinstance(artifact, KnowledgeArtifact):
        return artifact
    raise RuntimeError(
        "knowledge ingest step expected a KnowledgeArtifact from the previous "
        f"step, got {type(artifact).__name__}"
    )


def _emit(inp: StepInput, step: str, status: str, **extra: Any) -> None:
    """Fire the optional per-step progress callback; never let it break ingest."""
    cb = (inp.additional_data or {}).get("on_progress")
    if cb is None:
        return
    try:
        cb({"step": step, "status": status, **extra})
    except Exception:  # noqa: BLE001 — progress reporting must not abort the run
        pass


def _with_progress(name: str, executor: Callable[[StepInput], StepOutput]) -> Callable[[StepInput], StepOutput]:
    """Wrap a step executor so it emits start/done/error progress events."""

    def run(inp: StepInput) -> StepOutput:
        _emit(inp, name, "start")
        try:
            out = executor(inp)
        except Exception as exc:  # noqa: BLE001 — re-raised after reporting
            _emit(inp, name, "error", error=str(exc))
            raise
        _emit(inp, name, "done")
        return out

    return run


def fetch_step(inp: StepInput) -> StepOutput:
    return StepOutput(content=fetch(str(inp.input), category="temp-inbox"))


def clean_step(inp: StepInput) -> StepOutput:
    return StepOutput(content=clean_body(_artifact_from(inp)))


def enrich_step(inp: StepInput) -> StepOutput:
    return StepOutput(content=write_frontmatter(_artifact_from(inp)))


def classify_step(inp: StepInput) -> StepOutput:
    """Use a valid category override when supplied; else run the classifier agent."""
    artifact = _artifact_from(inp)
    override = (inp.additional_data or {}).get("category")
    if override:
        artifact.category = str(override)
        return StepOutput(content=artifact)
    return StepOutput(content=classify_category(artifact))


def persist_step(inp: StepInput) -> StepOutput:
    artifact = persist(_artifact_from(inp), ingest=_ingest_enabled(inp), locale=_locale(inp))
    if artifact.ingest_result and artifact.ingest_result.get("ok"):
        _mark_ingested(artifact)
    return StepOutput(content=artifact)


def _validate_category_override(category: str) -> None:
    """Reject a pinned category that is not a declared taxonomy path (loud, no fallback)."""
    valid = category_paths(load_taxonomy())
    if category not in valid:
        raise RuntimeError(
            f"unknown knowledge category: {category!r} (valid: {', '.join(valid)})"
        )


def ingest_one(
    value: str,
    *,
    ingest: bool = True,
    category: str | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    locale: str = DEFAULT_LOCALE,
) -> dict[str, Any]:
    """Ingest one URL or staged file into the wiki and optionally GBrain.

    `category` pins the destination wiki folder (skipping LLM classification);
    it is validated up front so a bad value fails before any fetch work.
    `on_progress` receives a `{step, status}` event around each pipeline step.
    `locale` (zh|en) sets the language of generated structural headings.
    """
    if category is not None:
        _validate_category_override(category)
    run_output = build().run(
        input=value,
        additional_data={
            "ingest": ingest,
            "category": category,
            "on_progress": on_progress,
            "locale": locale,
        },
    )
    return _build_result(_final_artifact(run_output), ingest_requested=ingest)


def _final_artifact(run_output) -> KnowledgeArtifact:
    artifact: KnowledgeArtifact | None = None
    for entry in run_output.step_results or []:
        if entry.success is False:
            raise RuntimeError(entry.error or str(entry.content))
        if isinstance(entry.content, KnowledgeArtifact):
            artifact = entry.content
    if artifact is None:
        raise RuntimeError("knowledge ingest produced no artifact")
    return artifact


def _build_result(artifact: KnowledgeArtifact, *, ingest_requested: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "source_type": artifact.source_type,
        "category": artifact.category,
        "markdown_path": str(artifact.clean_path) if artifact.clean_path else None,
        "raw_path": str(artifact.raw_path) if artifact.raw_path else None,
        "frontmatter": artifact.frontmatter,
    }
    if ingest_requested:
        result["ingest"] = artifact.ingest_result or {"ok": False, "error": "ingest result missing"}
    return result


def build() -> Workflow:
    """Construct the single-source knowledge ingest workflow."""
    return Workflow(
        id=WORKFLOW_ID,
        name="Knowledge Ingest",
        description=(
            "Fetch, edit, classify, write wiki markdown, and optionally index "
            "one knowledge input."
        ),
        steps=[
            Step(name="fetch", executor=_with_progress("fetch", fetch_step), max_retries=2, on_error=OnError.fail),
            Step(name="clean", executor=_with_progress("clean", clean_step), max_retries=1, on_error=OnError.fail),
            Step(name="enrich", executor=_with_progress("enrich", enrich_step), max_retries=1, on_error=OnError.fail),
            Step(name="classify", executor=_with_progress("classify", classify_step), max_retries=0, on_error=OnError.fail),
            Step(name="persist", executor=_with_progress("persist", persist_step), max_retries=0, on_error=OnError.fail),
        ],
        telemetry=False,
    )
