## Why

Knowledge ingestion is only ~10% localized. `localize-radar-analysis` threaded a
locale through the radar pipeline, and one follow-up commit localized the ingest
summary **heading** (`总结`/`Summary`) — but everything else a reader sees on an
ingested artifact is still hardcoded English or follows the source article's
language instead of the requested locale:

- the `Source:` / `Published:` / `Author:` labels baked into the body by the Folo
  staging HTML (and, as a side effect, `source_url` is lost from frontmatter for
  Folo ingests);
- the `## Related` heading;
- the frontmatter metadata table (English keys + enum values) rendered raw by the
  dashboard;
- the LLM `summary` and `title`, which follow the *source article's* language, not
  the locale the operator picked;
- tags, which are hardcoded English.

The result is that switching the dashboard to 中文 and ingesting yields a
mostly-English artifact. Users want an ingested item to read coherently in one
language, matching the locale it was ingested under.

The governing rule (agreed during design): **stored data is canonical and
locale-independent — except LLM-generated prose, which is stored in the locale the
backend was asked to generate. Every label/chrome is localized by the frontend at
display time, keyed by the item's own recorded locale so each item renders as a
self-consistent whole. Titles display translated, with the original preserved.**

## What Changes

- **A per-item `locale` stamp on knowledge artifacts** (frontmatter field),
  mirroring `radar_analyses.locale`. This *is* the "locale in DB": the dashboard
  keys every per-item label off it, so an item ingested under `zh` renders fully
  Chinese even under an English UI, and vice-versa. Switching the UI never
  retranslates existing items (no translate-on-view).
- **LLM `summary` and `title` follow the request locale.** `knowledge_frontmatter`
  (and `knowledge_github_summary`) become locale-aware via `build_from_name(name,
  locale)` and split into pure-language `.zh.md` / `.en.md` prompt variants. The
  locale threads dashboard → `paca knowledge ingest --locale` → workflow →
  `write_frontmatter`. **BREAKING** (behavioral): a Chinese-source article ingested
  under `en` now gets an English `summary`/`title`; today it gets Chinese.
- **The original title is preserved** as a new `source_title` frontmatter field, so
  the localized `title` never destroys the source's own words.
- **Structured provenance instead of body chrome.** `Source` / `Published` /
  `Author` move out of the injected staging HTML into structured frontmatter fields
  (`source_url`, `published`, `author`); the dashboard renders them with localized
  labels. This also fixes the current loss of `source_url` on Folo ingests.
- **Canonical body chrome.** The `## Summary` and `## Related` headings are written
  in one fixed language (English) in the `.md` — never keyed to the transient UI
  locale — and the dashboard swaps them to the item's locale at render. This
  reworks the current locale-baked `总结` heading into the canonical-file model.
- **Tags stay canonical English keys** (stable cross-language join keys in GBrain).
  A persisted `knowledge_tag_labels` translation-memory supplies the localized
  *display* label: each unique tag is translated once at ingest, stored, and reused;
  the render path is a pure lookup with English-key fallback. No per-render LLM.
- **The dashboard localizes per-item chrome by the item's stored `locale`:**
  frontmatter key labels, enum value labels, `## Summary` / `## Related` headings,
  `Source` / `Published` / `Author` labels, tag display labels, and which title to
  show. The UI cookie continues to drive only the app shell and the locale stamped
  on new ingests.

## Capabilities

### New Capabilities
<!-- none — this modifies existing capabilities -->

### Modified Capabilities
- `knowledge-pipeline`: `write_frontmatter` generates `summary`/`title` in the
  request locale via locale-aware `knowledge_frontmatter` / `knowledge_github_summary`
  prompt variants; artifacts gain a `locale` stamp and a preserved `source_title`;
  `source_url` / `published` / `author` become structured frontmatter fields; the
  `## Summary` / `## Related` headings are canonical (fixed-language) in the file;
  each unique tag is translated once into `knowledge_tag_labels`. The
  `paca knowledge ingest` command accepts `--locale <zh|en>` (default `en`).
- `core-database`: a `knowledge_tag_labels` table records `(tag, locale) -> label`
  display aliases, populated once per unique tag and read at render time.
- `dashboard-radar-reader`: the radar "Ingest to wiki" staging carries
  `source_url` / `published` / `author` as structured metadata (a `.meta.json`
  sidecar, not an English body block) and forwards the active UI locale into the
  ingest spawn.
- `dashboard-shell`: the `/knowledge` preview localizes an artifact's chrome —
  frontmatter key/value labels, `## Summary` / `## Related` headings, provenance
  labels, tag display labels, and the shown title — keyed by the artifact's stored
  `locale`, not the UI cookie.

## Impact

- **Prompts**: `prompts/agents/knowledge_frontmatter` and
  `knowledge_github_summary` → pure-language `.zh.md` + `.en.md` variants (no
  unsuffixed base); the `## 总结` reference in the summary rule is removed.
- **Pipeline**: `src/paca/workflows/knowledge_ingest.py` (thread `locale`),
  `stages/knowledge_ingest/artifact_editor.py` (`write_frontmatter(locale)`),
  `stages/knowledge_ingest/persist.py` (canonical `## Summary` heading, `source_title`
  + `locale` + provenance frontmatter, tag-label population),
  `stages/knowledge_ingest/related_section.py` (heading stays canonical), and
  `stages/knowledge_ingest/schemas.py` (`FrontmatterDraft` carries `source_title`).
- **Tag labels**: new `src/paca/tools/knowledge/` (or workflow stage) that ensures a
  label row per `(tag, locale)`; new `configs/agents/knowledge_tag_translator.yaml`
  + prompt (a tiny `local_structured`, `extra: {db: false, shared_context: false}`
  verifier-style agent).
- **CLI**: `src/paca/interfaces/cli.py` (`knowledge ingest --locale` validated,
  passed to the workflow) — the flag already exists for the summary heading; this
  extends its reach to the LLM agents and provenance.
- **Dashboard**: `dashboard/lib/radar-ingest.ts` (structured metadata, drop the
  English `Source/Published/Author` block), `dashboard/lib/actions/knowledge.ts` /
  `dashboard/lib/ingest/jobs.ts` (locale already forwarded — verify), `dashboard/lib/
  i18n/dictionaries.ts` (frontmatter key labels, enum value labels, provenance
  labels, heading labels), `dashboard/app/knowledge/page.tsx` (`FrontmatterPanel`
  localizes by item locale; title/tag display), `dashboard/components/radar/
  markdown-text.tsx` (swap canonical `## Summary` / `## Related` headings by item
  locale), and the tag-label lookup for chips.
- **Schema**: `scripts/bootstrap_db.py` (`knowledge_tag_labels` table via
  `CREATE TABLE IF NOT EXISTS`).
- **Docs**: `docs/modules/knowledge.md` (locale invariants: stored file canonical +
  LLM prose in ingest locale + per-item-locale display + tag translation memory),
  bilingual mirror `docs/zh/modules/knowledge.md`.
- No new runtime dependencies. Re-ingesting an existing artifact under a locale
  regenerates its LLM prose in that locale; a mere UI language switch does not.
