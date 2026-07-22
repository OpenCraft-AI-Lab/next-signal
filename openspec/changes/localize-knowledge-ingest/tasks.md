## 1. Schema: tag-label translation memory

- [x] 1.1 `scripts/bootstrap_db.py`: add `knowledge_tag_labels(tag TEXT, locale TEXT, label TEXT, created_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY(tag, locale))` via `CREATE TABLE IF NOT EXISTS`.

## 2. Prompts: locale-aware frontmatter agents

- [x] 2.1 Split `prompts/agents/knowledge_frontmatter.md` into pure-language `knowledge_frontmatter.zh.md` (Chinese `title`/`summary` rules) and `knowledge_frontmatter.en.md` (English), removing the `## 总结` mention and hard-asserting the output language of `title` / `summary`. Keep the `tags` rule as lowercase-English keys in both. (Both suffixed; no unsuffixed base.)
- [x] 2.2 Split `prompts/agents/knowledge_github_summary.md` into `.zh.md` / `.en.md` the same way (keep the four-perspective summary structure identical across variants).
- [x] 2.3 Confirm the YAML configs (`knowledge_frontmatter.yaml`, `knowledge_github_summary.yaml`) still name the logical stem in `instructions_file` (e.g. `agents/knowledge_frontmatter.md`) so the loader resolves the suffixed variant.

## 3. Schema field: preserve the source title

- [x] 3.1 `stages/knowledge_ingest/artifact.py`: add `source_title` to `KnowledgeArtifact` (+ `to_jsonable`), captured from the pre-LLM title in `write_frontmatter`. NOT a `FrontmatterDraft` field — the LLM must not echo the source title back (it would risk "improving" it and is redundant input).

## 4. Pipeline: thread locale + record provenance/locale/source_title

- [x] 4.1 `workflows/knowledge_ingest.py`: thread `locale` (default `en`) from `ingest_one` → `write_frontmatter` step (`enrich_step`) → `persist` step. (Locale already reached additional_data / persist; extended to the enrich agent.)
- [x] 4.2 `stages/knowledge_ingest/artifact_editor.py::write_frontmatter(artifact, *, locale)`: build the frontmatter agent via `build_from_name(agent_name, locale)`; set `artifact.source_title` from the pre-LLM title; keep `clean_body` locale-free.
- [x] 4.3 `stages/knowledge_ingest/persist.py`: write `locale` and `source_title` into frontmatter; derive the slug from `source_title` (not the localized `title`); `source_url` / `published` / `author` from `artifact.metadata` flow into frontmatter (metadata source_url overrides the URL-derived one).
- [x] 4.4 `stages/knowledge_ingest/persist.py::_append_summary_section`: always emit canonical `## Summary`; dedup regex still matches `总结|Summary`. `related_section.py` heading stays canonical `## Related`.
- [x] 4.5 `stages/knowledge_ingest/fetch.py`: when a staged (non-URL) source has a sibling `<stem>.meta.json`, read it and seed `artifact.metadata` with `source_url` / `published` / `author`.

## 5. Tag translation memory

- [x] 5.1 Add `configs/agents/knowledge_tag_translator.yaml` (`local_structured`, `extra: {db: false, shared_context: false}`) + `prompts/agents/knowledge_tag_translator.{zh,en}.md` (translate one English tag key to an idiomatic display label; proper nouns unchanged) + `TagLabel` schema.
- [x] 5.2 Add `ensure_tag_labels(tags, locale)` in `stages/knowledge_ingest/tag_labels.py`: `en` short-circuits (label == key); for each other `(tag, locale)` absent from `knowledge_tag_labels`, generate a label once and upsert; skip existing. Best-effort — log and continue on failure, never raise.
- [x] 5.3 Call `ensure_tag_labels` from `persist` after frontmatter is written.

## 6. CLI

- [x] 6.1 `interfaces/cli.py::knowledge ingest`: `--locale <zh|en>` (default `en`) validated and passed into `ingest_one(..., locale=)`; it now reaches `write_frontmatter` (title/summary), not just the heading. Help text updated.

## 7. Dashboard: staging + per-item-locale rendering

- [x] 7.1 `dashboard/lib/radar-ingest.ts`: drop the `Source:` / `Published:` / `Author:` block from `renderFoloEntryHtml`; write a sibling `<stem>.meta.json` (exported `foloEntryMetadata`) with `source_url` / `published` / `author` in `stageFoloEntry`. Test updated.
- [x] 7.2 `dashboard/lib/actions/radar.ts` (`ingestToWiki`): forwards the active locale → `startIngestJob` → argv `--locale` (already wired by the summary-heading commit; verified).
- [x] 7.3 `dashboard/lib/i18n/dictionaries.ts`: added `knowledge.frontmatter` static maps — key labels, enum value labels (`status`/`freshness`/`source_type`/`converter`/`locale`), and `Summary`/`Related` headings — for both locales.
- [x] 7.4 `dashboard/app/knowledge/page.tsx`: `ActivePreview` renders the whole preview in the artifact's `frontmatter.locale` (fallback UI locale); `FrontmatterPanel` localizes key + enum-value labels; `MarkdownText` gets `headingLocale`.
- [x] 7.5 `dashboard/components/radar/markdown-text.tsx`: optional `headingLocale` swaps canonical `## Summary` / `## Related` at render (radar callers unaffected).
- [x] 7.6 Tag chips: `dashboard/lib/knowledge/tag-labels.ts::getTagLabels(tags, item.locale)` (server read, best-effort) → chips render the label with English-key fallback (header + frontmatter panel).

## 8. Docs

- [x] 8.1 `docs/modules/knowledge.md` + `docs/zh/modules/knowledge.md`: added the localization invariant (canonical storage + LLM prose in ingest locale + per-item `locale` display + `source_title` slug + `knowledge_tag_labels` + variants-in-sync), the agent-table rows, and the canonical `## Summary` note.

## 9. Verification

- [x] 9.1 `uv run pytest -q` green — 349 passed, 13 skipped. New/updated: `source_title` on the artifact + slug-from-source_title; canonical `## Summary` under zh; `locale`/`source_title` in frontmatter; sidecar seeds provenance; `knowledge_frontmatter` / `knowledge_tag_translator` resolve distinct `zh`/`en` prompt files. ruff clean on all changed Python.
- [ ] 9.2 Containerized end-to-end per CLAUDE.md: `docker compose build`; ingest a URL with `--locale zh` and confirm the `.md` has canonical `## Summary`, `locale: zh`, `source_title`, `source_url` in frontmatter, Chinese `title`/`summary`, English tag keys, and a `knowledge_tag_labels` zh row per tag; repeat with `--locale en`. **Deferred — needs Docker + live OMLX + Postgres.**
- [ ] 9.3 Dashboard: with UI `en`, open a `zh`-stamped artifact and confirm it renders fully Chinese (labels + headings + tag labels + title) without retranslating on UI toggle; confirm a Folo ingest stores `source_url` in frontmatter (not lost). **Deferred — needs Docker stack + `npm install` for the TS typecheck.**
