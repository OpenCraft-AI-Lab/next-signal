## MODIFIED Requirements

### Requirement: `paca knowledge ingest` accepts URLs and files

The CLI command `paca knowledge ingest <url|file>` SHALL detect the source type (microblog article, YouTube, Bilibili, PDF, Office, HTML, image, plain markdown) and route to the matching adapter. The command SHALL accept an optional `--category <path>` flag that pins the destination wiki folder, an optional `--progress` flag that emits one JSON event per pipeline step to stdout, and an optional `--locale <zh|en>` flag (default `en`) that sets the language of LLM-generated content (`title`, `summary`) and the artifact's recorded `locale`. An invalid `--locale` value SHALL be rejected loud. With `--category`, `--progress`, and `--locale` absent the command behaves as automatic classification, a single result-JSON line on stdout, and the `en` default locale.

#### Scenario: WeChat article saved

- **WHEN** `paca knowledge ingest https://mp.weixin.qq.com/s/<id>` is run
- **THEN** the OpenCLI adapter downloads the article + images to the raw store, rewrites image references to local relative paths, and emits clean markdown

#### Scenario: YouTube video saved

- **WHEN** the input URL is a YouTube link
- **THEN** the MarkItDown adapter writes the converted markdown and a raw conversion JSON

#### Scenario: category pinned via flag

- **WHEN** `paca knowledge ingest <url> --category knowledge/ai-ml` is run with a path present in the taxonomy
- **THEN** the artifact is written under that folder and the LLM classification step is skipped

#### Scenario: unknown category rejected

- **WHEN** `paca knowledge ingest <url> --category not/a/real/path` is run
- **THEN** the command fails loud with a non-zero exit before performing the ingest work

#### Scenario: progress events streamed

- **WHEN** `paca knowledge ingest <url> --progress` is run
- **THEN** stdout contains one JSON event line per pipeline step as each step starts and completes, followed by the final result JSON as the last line, with all lines forming valid JSONL

#### Scenario: locale flag sets the generation language

- **WHEN** `paca knowledge ingest <url> --locale zh` is run
- **THEN** the artifact's `title` and `summary` are generated in Chinese and the artifact records `locale: zh`

#### Scenario: locale defaults to English

- **WHEN** `paca knowledge ingest <url>` is run with no `--locale`
- **THEN** the pipeline behaves as `--locale en`

## ADDED Requirements

### Requirement: Ingest locale drives generated-content language

`ingest_one` and the ingest workflow SHALL accept a `locale` (one of `zh`, `en`; runtime default `en`) and thread it to `write_frontmatter`, which SHALL build its frontmatter agent with that locale (`build_from_name("knowledge_frontmatter", locale)`, or `knowledge_github_summary` for github sources). The generated `title` and `summary` SHALL be in the request locale regardless of the source article's language. Each frontmatter agent's prompt SHALL exist as pure-language `zh` and `en` variants (no single mixed prompt). The body cleaner (`knowledge_artifact_editor` / `knowledge_github_cleaner`) SHALL NOT take a locale — it cleans the body in place and preserves the body's source language.

#### Scenario: English source under a Chinese locale

- **WHEN** an English-language article is ingested with `locale="zh"`
- **THEN** the generated `title` and `summary` are Chinese, while the cleaned body remains in its original English

#### Scenario: frontmatter agent selects the locale-matched prompt

- **WHEN** `write_frontmatter` runs under `locale="en"`
- **THEN** it builds the frontmatter agent with the English prompt variant and the Chinese variant is not used

#### Scenario: body cleaner preserves source language

- **WHEN** `clean_body` runs on a Chinese article under `locale="en"`
- **THEN** the cleaned body stays Chinese (the cleaner is not locale-parameterized)

### Requirement: Artifacts record their locale and preserve the source title

Each ingested artifact SHALL record a `locale` frontmatter field (the request locale, `zh` | `en`) identifying the language its generated content was produced in, and a `source_title` frontmatter field preserving the pre-LLM source title. The wiki filename / slug SHALL derive from `source_title`, NOT from the localized `title`, so the same source ingested under different locales keeps a stable slug and GBrain identity. `FrontmatterDraft` SHALL carry `source_title`.

#### Scenario: locale and source title are persisted

- **WHEN** an artifact is ingested with `locale="zh"` from a source titled "Attention Is All You Need"
- **THEN** the frontmatter contains `locale: zh`, a Chinese `title`, and `source_title: "Attention Is All You Need"`

#### Scenario: slug is stable across locales

- **WHEN** the same source is ingested once under `en` and once under `zh`
- **THEN** both resolve to the same wiki slug (derived from `source_title`) and the second ingest overwrites the first in place rather than forking a new file

### Requirement: Provenance is stored as structured frontmatter

Source provenance (`source_url`, `published`, `author`) SHALL be stored as structured frontmatter fields rather than as an English label block inside the body. When a staged source file has a sibling `<stem>.meta.json` sidecar, the fetch step SHALL read it and seed `artifact.metadata` with those fields. `source_url` SHALL be populated in frontmatter for Folo-staged ingests (whose input is a file path, not the original URL).

#### Scenario: staged sidecar seeds provenance

- **WHEN** a staged `.html` file has a sibling `.meta.json` carrying `source_url` / `published` / `author` and is ingested
- **THEN** those values appear as frontmatter fields and no `Source:` / `Published:` / `Author:` label block is present in the body

#### Scenario: Folo ingest retains its source URL

- **WHEN** a Folo radar item is staged and ingested
- **THEN** the resulting frontmatter carries the original article `source_url` (not null)

### Requirement: Body structural headings are canonical

The auto-generated `## Summary` and `## Related` section headings SHALL be written in one fixed language (English) in the stored `.md`, never keyed to the request or UI locale. `_append_summary_section` SHALL always write `## Summary`; its dedup guard SHALL still match a pre-existing `## 总结` or `## Summary` heading so re-ingest never double-appends. The summary prose under the heading remains generated content in the request locale.

#### Scenario: summary heading is canonical English

- **WHEN** an artifact is ingested with `locale="zh"`
- **THEN** the stored `.md` contains `## Summary` (not `## 总结`) followed by Chinese summary prose

#### Scenario: re-ingest does not double-append the summary

- **WHEN** an artifact that already carries a `## 总结` or `## Summary` section is re-ingested
- **THEN** the summary guard matches the existing heading and no second summary section is appended

### Requirement: Tag display labels via a persisted translation memory

Tags SHALL remain lowercase English keys (unchanged). After frontmatter is written, the pipeline SHALL ensure a display label exists for each `(tag, locale)` pair in the `knowledge_tag_labels` store: for a pair not already present, a dedicated `knowledge_tag_translator` agent SHALL produce the localized label once and it SHALL be persisted; existing pairs SHALL be skipped (no regeneration). Label generation SHALL be best-effort — a translation failure SHALL be logged and degrade to the English key, and SHALL NOT fail the ingest.

#### Scenario: each new tag is translated once and reused

- **WHEN** an artifact with tags `[multimodal, deepseek]` is ingested under `locale="zh"` and neither pair exists yet
- **THEN** a `zh` label is generated once per tag and stored in `knowledge_tag_labels`; a later ingest carrying the same tags under `zh` generates no new translations

#### Scenario: tag translation failure does not fail the ingest

- **WHEN** the tag translator errors for a tag
- **THEN** the failure is logged, the tag has no stored label (rendering will fall back to the English key), and the artifact is still written successfully
