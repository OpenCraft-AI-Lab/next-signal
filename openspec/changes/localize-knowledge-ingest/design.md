## Context

The knowledge-ingest pipeline turns a URL / staged file into (1) a canonical
markdown artifact in the wiki, (2) a raw archive copy, and (3) a GBrain index
entry. Its LLM steps run through `configs/agents/knowledge_*.yaml` +
`prompts/agents/*`; `write_frontmatter` produces `title` / `summary` / `tags` /
`freshness` under the `FrontmatterDraft` schema; `persist` builds frontmatter and
writes the `.md`. The dashboard renders an artifact in the `/knowledge` preview
(`ActivePreview` → `FrontmatterPanel` + `MarkdownText`).

`localize-radar-analysis` already made the agent loader locale-aware
(`build_from_name(name, locale)` resolving `<stem>.<locale>.md` with an unsuffixed
base fallback) and set `paca.core.config.DEFAULT_LOCALE = "en"`. One commit made the
ingest summary heading locale-aware (`_append_summary_section(locale)` picking
`总结`/`Summary`). This change reuses the loader capability and reworks that heading
into the canonical-file model below.

The call chain that must carry the ingest locale (the summary-heading commit already
threads it as far as `persist`; this change extends it to the LLM agents):

```
UI locale (paca_locale)
  └─ ingestToWiki(locale) / IngestForm
       └─ paca knowledge ingest --locale <zh|en>
            └─ ingest_one(..., locale)
                 └─ write_frontmatter(artifact, locale)   [new: build agent with locale]
                      └─ build_from_name("knowledge_frontmatter", locale)
                 └─ persist(artifact, locale)             [source_title/locale/provenance frontmatter]
                      └─ ensure_tag_labels(tags, locale)  [new: translation memory]
```

Project constraints: agent behavior lives in `configs/` YAML (Python defines shape);
loader enforces `config stem == name:`; business tables use bare `psycopg` with DDL
in `scripts/bootstrap_db.py`; the `.md` is also an Obsidian/GBrain artifact and must
stay machine-parseable; failures are loud (`RuntimeError`), no silent fallbacks.

## Goals / Non-Goals

**Goals:**
- An ingested artifact reads coherently in the locale it was ingested under: its
  LLM prose (summary/title) is in that locale and every label/heading the dashboard
  shows is in that locale.
- Each artifact records its own `locale`; the dashboard localizes per-item chrome by
  that stamp, so a mixed-language wiki renders each item self-consistently.
- The stored `.md` stays a canonical, machine-parseable artifact: English frontmatter
  keys, English enum tokens, English tag keys, fixed-language structural headings.
- The source's original title is never lost.

**Non-Goals:**
- No translate-on-view. Switching the UI language does not retranslate stored items;
  to get an item in the other language you re-ingest under that locale.
- No translation of the verbatim article **body** — an English article ingested
  under `zh` keeps its English body (a Chinese wrapper over English source). Full
  machine translation of article bodies is out of scope.
- No localization of tag **keys** (they stay English join keys); only a display
  alias is added.
- No new supported languages beyond `zh` / `en`.

## Decisions

### D1: Per-item `locale` stamp drives per-item display; UI cookie drives the shell

Two independent locale drivers. The **item's stored `locale`** (frontmatter, set at
ingest from the `--locale` param) governs how *that item* renders: its LLM prose is
already in that locale, and the dashboard chooses every label/heading/tag-alias/title
by it. The **UI cookie** governs only the app shell (nav, page titles, buttons,
forms) and the locale stamped on *new* ingests. Consequence: an item never changes
language on a UI toggle; a page becomes a mix of self-consistent items. This matches
`localize-radar-analysis`'s "mixed-language corpus by design" and the user rule
"if the locale in DB shows EN, the display matches EN."

**Alternative considered:** localize per the UI cookie at display. Rejected — it
produces Frankenstein items (English labels over Chinese prose) and implies
translate-on-view for the prose.

### D2: LLM prose follows the request locale via pure-language prompt variants

`write_frontmatter` builds its agent with the ingest locale:
`build_from_name("knowledge_frontmatter", locale)` (and `knowledge_github_summary`
for github). Each prompt splits into `.zh.md` / `.en.md` pure-language variants (no
unsuffixed base), mirroring the radar prompt split. The summary rule drops its
`## 总结` mention (the heading is chrome, decided in D4) and each variant hard-asserts
its output language regardless of source-article language. `knowledge_artifact_editor`
/ `knowledge_github_cleaner` stay **single-language / unsuffixed** — they clean the
body in place and must preserve its source language, so they take no locale.

**Alternative considered:** inject a "reply in <lang>" footnote into one prompt.
Rejected for the same reason radar rejected it — pure-language files read and
maintain better, and the user asked for pure-language prompts.

### D3: `source_title` preserves the original; `title` is localized

`FrontmatterDraft` gains `source_title` (the pre-LLM source title). `persist` writes
both: `title` (LLM, in the item locale) and `source_title` (verbatim source). The
wiki filename derives from `source_title` — NOT the localized `title` — so the same
article ingested under different locales keeps a stable slug / GBrain identity and
the collision/idempotency logic in `persist` is unaffected.

**Alternative considered:** derive the filename from the localized `title`. Rejected —
it would fork one article into two files across locales and break re-ingest
idempotency.

### D4: Canonical body chrome in the file; dashboard swaps headings by item locale

The `## Summary` and `## Related` headings are written in one fixed language
(**English**) in the `.md`, never keyed to the UI locale. `_append_summary_section`
stops choosing `总结`/`Summary` by locale and always writes `## Summary`; its
dedup regex still matches either language so historical `## 总结` files are not
double-appended. `render_related_section` keeps `## Related`. The dashboard's
`MarkdownText` swaps these two known auto-generated headings to the item's locale at
render. The summary *prose* under the heading is LLM content (in the item locale);
Obsidian sees an English heading over locale prose — an accepted minor mixing for the
canonical file (D1 makes the dashboard consistent).

**Alternative considered:** keep baking the heading in the ingest locale (the current
`总结` behavior). Rejected — it keys stored chrome to the transient UI locale and
leaves the dashboard unable to re-localize; canonical-file + display-swap is the
user's chosen model.

### D5: Provenance is structured frontmatter, not an English body block

`renderFoloEntryHtml` stops emitting the `<strong>Source/Published/Author</strong>`
block into the staged HTML. Instead the radar "Ingest to wiki" action carries
`source_url`, `published`, `author` as structured metadata into the ingest, and
`persist` writes them as frontmatter fields. The dashboard renders them as rows with
localized labels. This also fixes a latent bug: Folo ingests stage a *file* path, so
`persist` currently derives `source_url = None` and the URL survives only inside the
body text — moving it to frontmatter restores it as data.

**Mechanism for carrying metadata through the file-based ingest:** the staging step
writes a sidecar `radar-<id>.meta.json` next to the staged `.html`, and `fetch_web`
reads a sibling `<stem>.meta.json` when present, seeding `artifact.metadata`
(`source_url` / `published` / `author`). Chosen over new CLI flags to keep the CLI
surface small and because the dashboard already writes the staged file; the sidecar
is co-located and self-cleaning with the tmp dir.

**Alternative considered:** add `--source-url` / `--published` / `--author` CLI flags.
Rejected — widens the CLI for a dashboard-only staging concern.

### D6: Tags stay English keys; a persisted translation memory supplies display labels

Tag **keys** remain lowercase English (unchanged prompt rule) so GBrain cross-language
joins stay intact. A `knowledge_tag_labels(tag TEXT, locale TEXT, label TEXT,
PRIMARY KEY(tag, locale))` table holds display aliases. At ingest, `persist` (after
frontmatter) calls `ensure_tag_labels(tags, locale)`: for each `(tag, locale)` not
present, a tiny `knowledge_tag_translator` agent produces the localized label once and
the row is stored; existing rows are skipped. Because supported locales are `{en, zh}`
and `en` == the key, only a single zh translation per unique tag is ever generated.
The dashboard render is a pure lookup: `label(tag, item.locale)` → row, else the
English key. No LLM on the render path; a missing row degrades to the key (and MAY be
backfilled).

**Alternative considered:** LLM-localized tag keys per locale, or a static hand-authored
map. Rejected — localized keys fragment GBrain; a static map can't cover open-vocabulary
tags.

### D7: Dashboard chrome maps are static except tags

Frontmatter **keys** (`title`, `source_type`, `status`, …) and **enum values**
(`clean`, `markitdown`, freshness tiers, source types) are closed vocabularies →
hand-authored `dictionaries.ts` maps, keyed by item locale, zero runtime cost, stored
YAML unchanged. Only tags (open vocabulary, D6) need the persisted translation memory.
`FrontmatterPanel` renders `keyLabel(key, item.locale)` and, for enum-valued fields,
`valueLabel(key, value, item.locale)`; non-enum values (dates, urls, digest) render
raw.

## Risks / Trade-offs

- **Rework of the shipped `总结` heading** → The summary-heading commit's locale
  branch is replaced by canonical `## Summary` + dashboard swap. Historical files
  with `## 总结` keep rendering (the dashboard swap matches either; the dedup regex
  matches either). Low risk, explicitly covered by a test.
- **Mixed heading language in the stored file** (English heading over locale prose in
  Obsidian) → Accepted per D4; the dashboard is consistent, and Obsidian users see a
  minor cosmetic mix.
- **`FrontmatterDraft` gains `source_title`** → an added optional field; existing
  rows without it fall back to the source title already carried on the artifact.
- **Tag-translator adds an LLM call at ingest** → bounded to once per *new* tag ever;
  a failure MUST NOT fail the ingest (label is best-effort display chrome) — degrade
  to the English key and log, unlike the loud-failure policy for core artifact fields.
- **Prompt rubric drift between `.zh.md` / `.en.md`** → mitigate by keeping the field
  list / rules structurally identical across variants; call it out in
  `docs/modules/knowledge.md`.
- **Re-ingest regenerates prose in the new locale** → intended (D1); the file's
  `locale` stamp and slug stay coherent because the slug derives from `source_title`
  (D3), not the localized title.

## Migration Plan

1. Schema: `knowledge_tag_labels` via `CREATE TABLE IF NOT EXISTS` in
   `scripts/bootstrap_db.py`.
2. Prompts: split `knowledge_frontmatter` + `knowledge_github_summary` into
   `.zh.md` / `.en.md`; drop the `## 总结` mention; hard-assert output language.
3. Schema field: `FrontmatterDraft.source_title`; `to_artifact_edit()` carries it.
4. Pipeline: thread `locale` into `write_frontmatter` (agent build) and `persist`
   (`source_title`, `locale` stamp, provenance frontmatter, canonical `## Summary`,
   `ensure_tag_labels`). `related_section` heading stays `## Related`.
5. Tag memory: `knowledge_tag_translator` agent + prompt; `ensure_tag_labels`.
6. Dashboard: sidecar metadata in `radar-ingest.ts`; `fetch_web` reads the sidecar;
   `dictionaries.ts` chrome maps; `FrontmatterPanel` + `MarkdownText` localize by
   item locale; tag chips use the label lookup.
7. CLI: confirm `knowledge ingest --locale` validates and reaches `write_frontmatter`.
8. Docs (`docs/modules/knowledge.md` + `docs/zh/…`) + tests.

**Rollback:** reverting the code restores the current behavior; `knowledge_tag_labels`
and the `source_title` / `locale` frontmatter fields can remain (unused) with no data
loss — they are additive.

## Open Questions

- Should a future dashboard control let the operator re-ingest an existing artifact
  in the other locale from the preview pane (an explicit "generate 中文 version")?
  Out of scope here; the `locale` stamp + slug-from-`source_title` make it possible.
- Should `knowledge_reviews` cards (which reuse frontmatter `summary`) also localize
  their chrome by the doc's `locale`? Likely yes for consistency; scoped as a small
  follow-on once the frontmatter `locale` stamp exists.
