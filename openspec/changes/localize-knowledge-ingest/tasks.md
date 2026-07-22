## 1. Schema: tag-label translation memory

- [ ] 1.1 `scripts/bootstrap_db.py`: add `knowledge_tag_labels(tag TEXT, locale TEXT, label TEXT, created_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY(tag, locale))` via `CREATE TABLE IF NOT EXISTS`.

## 2. Prompts: locale-aware frontmatter agents

- [ ] 2.1 Split `prompts/agents/knowledge_frontmatter.md` into pure-language `knowledge_frontmatter.zh.md` (Chinese `title`/`summary` rules) and `knowledge_frontmatter.en.md` (English), removing the `## 总结` mention and hard-asserting the output language of `title` / `summary`. Keep the `tags` rule as lowercase-English keys in both. (Both suffixed; no unsuffixed base.)
- [ ] 2.2 Split `prompts/agents/knowledge_github_summary.md` into `.zh.md` / `.en.md` the same way (keep the four-perspective summary structure identical across variants).
- [ ] 2.3 Confirm the YAML configs (`knowledge_frontmatter.yaml`, `knowledge_github_summary.yaml`) still name the logical stem in `instructions_file` (e.g. `agents/knowledge_frontmatter.md`) so the loader resolves the suffixed variant.

## 3. Schema field: preserve the source title

- [ ] 3.1 `stages/knowledge_ingest/schemas.py`: add `source_title` to `FrontmatterDraft` and include it in `to_artifact_edit()`.

## 4. Pipeline: thread locale + record provenance/locale/source_title

- [ ] 4.1 `workflows/knowledge_ingest.py`: thread `locale` (default `en`) from `ingest_one` → `write_frontmatter` step → `persist` step (mirror the existing summary-heading locale threading).
- [ ] 4.2 `stages/knowledge_ingest/artifact_editor.py::write_frontmatter(artifact, locale)`: build the frontmatter agent via `build_from_name(agent_name, locale)`; set `artifact.source_title` from the pre-LLM title; keep `clean_body` locale-free.
- [ ] 4.3 `stages/knowledge_ingest/persist.py`: write `locale` and `source_title` into frontmatter; derive the slug from `source_title` (not the localized `title`); write `source_url` / `published` / `author` from `artifact.metadata` as frontmatter fields.
- [ ] 4.4 `stages/knowledge_ingest/persist.py::_append_summary_section`: always emit canonical `## Summary`; keep the dedup regex matching `总结|Summary`. `related_section.py` heading stays canonical `## Related`.
- [ ] 4.5 `stages/knowledge_ingest/fetch.py` (`fetch_web` / staged-file path): when a staged source has a sibling `<stem>.meta.json`, read it and seed `artifact.metadata` with `source_url` / `published` / `author`.

## 5. Tag translation memory

- [ ] 5.1 Add `configs/agents/knowledge_tag_translator.yaml` (`local_structured`, `extra: {db: false, shared_context: false}`, tight `max_tokens`) + `prompts/agents/knowledge_tag_translator.{zh,en}.md` (translate one English tag key to an idiomatic display label; proper nouns unchanged).
- [ ] 5.2 Add `ensure_tag_labels(tags, locale)` (tool or persist helper): for each `(tag, locale)` absent from `knowledge_tag_labels`, generate a label once and upsert; skip existing. Best-effort — log and continue on failure, never raise.
- [ ] 5.3 Call `ensure_tag_labels` from `persist` after frontmatter is written.

## 6. CLI

- [ ] 6.1 `interfaces/cli.py::knowledge ingest`: confirm `--locale <zh|en>` (default `en`) is validated and passed into `ingest_one(..., locale=)` so it reaches `write_frontmatter` (today it only reaches the summary heading).

## 7. Dashboard: staging + per-item-locale rendering

- [ ] 7.1 `dashboard/lib/radar-ingest.ts`: drop the `Source:` / `Published:` / `Author:` block from `renderFoloEntryHtml`; write a sibling `<stem>.meta.json` with `source_url` / `published` / `author` in `stageFoloEntry`.
- [ ] 7.2 `dashboard/lib/actions/radar.ts` (`ingestToWiki`): forward the active locale as `--locale` into the ingest spawn (verify it already threads to `startIngestJob`).
- [ ] 7.3 `dashboard/lib/i18n/dictionaries.ts`: add static maps — frontmatter key labels, enum value labels (`status` / `freshness` / `source_type` / `converter`), provenance labels (`source`/`published`/`author`), and `## Summary` / `## Related` heading labels — for both locales.
- [ ] 7.4 `dashboard/app/knowledge/page.tsx` (`FrontmatterPanel` / `ActivePreview`): localize key + enum-value labels by the artifact's `frontmatter.locale` (fallback UI locale); render provenance rows; show localized `title`.
- [ ] 7.5 `dashboard/components/radar/markdown-text.tsx`: swap canonical `## Summary` / `## Related` headings to the passed item locale at render.
- [ ] 7.6 Tag chips: look up `knowledge_tag_labels` for `(tag, item.locale)` (server read) and render the label with English-key fallback.

## 8. Docs

- [ ] 8.1 `docs/modules/knowledge.md` + `docs/zh/modules/knowledge.md`: add the localization invariants — stored `.md` canonical (English keys/tokens/tag-keys/headings) + LLM prose in ingest locale + per-item `locale` stamp drives display + `source_title` preserved + `knowledge_tag_labels` translation memory + prompt `.zh.md`/`.en.md` variants must stay structurally in sync.

## 9. Verification

- [ ] 9.1 `uv run pytest -q` green, including: `FrontmatterDraft.source_title`; the summary-guard dedup still matches `## 总结`; slug derives from `source_title`; `ensure_tag_labels` upserts once and is best-effort; the real `knowledge_frontmatter` / `knowledge_github_summary` configs resolve distinct `zh`/`en` prompt files.
- [ ] 9.2 Containerized end-to-end per CLAUDE.md: `docker compose build`; ingest a URL with `--locale zh` and confirm the `.md` has canonical `## Summary`, `locale: zh`, `source_title`, `source_url` in frontmatter, Chinese `title`/`summary`, English tag keys, and a `knowledge_tag_labels` zh row per tag; repeat with `--locale en`.
- [ ] 9.3 Dashboard: with UI `en`, open a `zh`-stamped artifact and confirm it renders fully Chinese (labels + headings + tag labels + title) without retranslating on UI toggle; confirm a Folo ingest stores `source_url` in frontmatter (not lost).
