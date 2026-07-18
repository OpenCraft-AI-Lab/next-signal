## Context

The current knowledge pipeline already produces the right durable outcome: a raw archive, a clean wiki markdown artifact, optional frontmatter enrichment, and optional GBrain ingest that must not destroy the artifact when it fails. The implementation is still stage-heavy: the Agno workflow mostly adapts deterministic Python functions into `Step` and `Router` wrappers, while the actual agent behavior is hidden inside clean and enrichment helper functions.

This change keeps the existing artifact contract but moves the main orchestration into Agno agents. The key constraint is that agentic orchestration must not weaken the current guardrails around local file access, public-web SSRF checks, validation, wiki writes, and GBrain ingest.

## Goals / Non-Goals

**Goals:**

- Make the single-item knowledge ingest flow agent-led instead of Python-stage-led.
- Keep large markdown context out of the orchestrator by adding a dedicated artifact editor agent.
- Preserve the current JSON result shape through `paca knowledge ingest`.
- Preserve raw artifact storage, clean wiki writes, frontmatter fields, related links, and optional GBrain ingest.
- Keep deterministic tools in charge of security-sensitive and side-effecting operations.
- Keep validation strong enough to catch empty edits, transcript summarization, heading invention, and invalid frontmatter.
- Fail loud when required LLM editing fails or produces invalid output instead of writing deterministic fallback content.

**Non-Goals:**

- Keep weekly wiki re-index behavior, but share the same wiki-relative GBrain page identity as direct ingest.
- Do not introduce a new external dependency.
- Do not let an agent directly read arbitrary local files, fetch arbitrary URLs, write wiki files, or invoke GBrain.
- Do not remove existing source adapters for WeChat, Bilibili, YouTube, MarkItDown-supported files, markdown files, or public web pages.
- Do not change the wiki/raw directory layout or GBrain slug semantics.

## Decisions

### Use an orchestrator agent for flow control

Add a `knowledge_orchestrator` agent that receives the user input, category, `enrich`, and `ingest` flags. It calls deterministic tools in order, handles retry decisions after validation failures, and returns the final JSON result.

Alternative considered: keep the existing `Workflow` step chain and only rename stages. That would preserve the current complexity and would not make the pipeline meaningfully more agentic.

### Use one artifact editor agent for clean markdown and frontmatter

Add a `knowledge_artifact_editor` agent that receives the fetched source packet, including title, source type, public metadata, markdown, and optional transcript context. It returns a single JSON object containing cleaned markdown plus `title`, `summary`, `tags`, `freshness`, and `related_queries`.

This replaces the current split between cleaner, transcript cleaner, and frontmatter enricher in the main path. The editor sees the full content once, which keeps the orchestrator context small and lets title/summary/tags reflect the final cleaned body.

Alternative considered: keep separate cleaner and frontmatter agents. That has cleaner responsibilities, but it duplicates context and keeps more orchestration in Python.

### Keep deterministic tools for boundaries

The following work remains in Python tools:

- Source classification and fetch, including staged-file enforcement and SSRF-safe public web fetch.
- Raw archive writes.
- Validation of edited markdown and frontmatter.
- Related GBrain search.
- Wiki artifact write, frontmatter rendering, slug calculation, and transcript record write.
- GBrain ingest and error capture.

These operations are not agent responsibilities because they need stable, testable behavior and clear failure modes.

### Do not use deterministic content fallback for LLM editing

If `knowledge_artifact_editor` fails, times out, returns invalid JSON, returns empty cleaned markdown, or fails validation after the configured retry, the save operation fails loudly. The pipeline must not generate a simplified artifact from deterministic summary/tag/title logic as a substitute for the LLM edit.

Deterministic code may still validate output, normalize accepted markdown structurally, write files, calculate slugs, and report errors. It must not invent replacement content for the body or frontmatter after a required LLM step fails.

### Put wiki writes inside the knowledge ingest workflow

`knowledge_ingest` is the source-of-truth workflow for single-input ingestion: fetch the source, edit the artifact, write the wiki markdown, and optionally index it in GBrain. The CLI command `paca knowledge ingest` calls this workflow and returns `ok`, `source_type`, `category`, `markdown_path`, `raw_path`, `frontmatter`, and optional `ingest`.

The manager-facing tool is `knowledge_ingest_workflow`; low-level `gbrain_ingest` is not part of the default `knowledge_manager` toolset.

### Use wiki-relative-derived GBrain slugs

Direct single-input ingest and weekly wiki re-index both derive the GBrain slug from `clean_path.relative_to(WIKI_DIR).with_suffix("")`, then pass it through the GBrain-safe slug normalizer. This keeps the wiki file as source of truth and prevents duplicate pages when the weekly re-index sees a file previously created by direct ingest, while respecting the GBrain CLI's lowercase slash-free slug constraint.

## Risks / Trade-offs

- Agent returns over-cleaned or summarized markdown → validate retention, transcript heading preservation, and invented headings before writing.
- Artifact editor prompt becomes too broad → keep output schema narrow and reject invalid frontmatter in deterministic validation.
- Orchestrator hides failures in prose → require final structured JSON and convert tool failures into loud `RuntimeError` except for GBrain ingest.
- LLM/editor is unavailable → fail the save before writing the clean artifact; keep raw fetch artifacts only if they were already captured by the fetch tool.
- Validation retry loops become expensive → cap editor retries, initially one retry after validation feedback.
- Migration breaks CLI callers → keep the ingest JSON result shape stable and add tests.
- Direct ingest and weekly re-index create duplicate GBrain pages → use the same wiki-relative-derived GBrain-safe slug in both paths.
- GBrain outage masks artifact problems → preserve current behavior: write artifact first, record ingest failure separately.

## Migration Plan

1. Add `knowledge_artifact_editor` and `knowledge_orchestrator` configs and prompts.
2. Introduce small deterministic tools for source fetch, artifact edit validation, artifact write, related search, and GBrain ingest where current stage functions can be reused.
3. Route `paca knowledge ingest` through the workflow while preserving the public result shape.
4. Keep legacy cleaner/enricher code available only as implementation reference until equivalent tests pass; do not wire them as fallback content generators.
5. Update tests around source fetch, editor validation retry, artifact write, ingest failure, and final output compatibility.
6. Validate with `uv run pytest -q` and a scoped full-flow smoke using an isolated test GBrain when available.

Rollback is straightforward: keep the old workflow path behind the existing function boundary until the new path is verified, then remove the old stage chain in the same implementation change.

## Open Questions

- Should the compatibility `knowledge_pipeline_workflow` alias be removed after downstream users move to `knowledge_ingest_workflow`?
