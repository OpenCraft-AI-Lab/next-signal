## Context

Radar analysis output language is currently pinned to the language of
`configs/info_radar/goals.yaml` — every prompt ends with a "match the language of
`goals`" instruction, and tier-2 additionally uses a "你/you" heuristic. The
dashboard already carries a locale (`paca_locale` cookie, `LOCALES = ["zh","en"]`,
`DEFAULT_LOCALE = "zh"`), and `runPullAndAnalyze(localeValue)` already receives it —
but the locale is dropped before the `paca info-radar analyze` spawn, so it never
reaches the pipeline. Switching the dashboard language localizes only the chrome.

The call chain that must become locale-aware:

```
UI locale (paca_locale)
  └─ runPullAndAnalyze(locale)
       └─ spawn("uv","run","paca","info-radar","analyze")      [drops locale today]
            └─ cli.info_radar_analyze(limit, source)           [no --locale]
                 └─ runner.run(limit, source)                  [no locale]
                      └─ tier1.run / tier2.run / dedup.run     [no locale]
                           └─ build_from_name("radar_<stage>") [hardcoded name]
                                └─ insert_analysis(...)         [no locale column]
```

Constraints from the project: agent behavior lives in `configs/` YAML (Python
defines shape); the loader enforces `config stem == name:` strictly; analysis
agents use the `local_structured` profile with `extra: {db: false,
shared_context: false}` and a tight `max_tokens: 4096`; business tables use bare
`psycopg` and DDL lives in `scripts/bootstrap_db.py`.

## Goals / Non-Goals

**Goals:**
- Generated radar analysis content (tier-1 reason, tier-2 summary/impact) follows
  the UI-selected locale, end-to-end from the dashboard.
- Prompts are pure-language per variant (de-mix the current EN/CN prompts).
- Both prompt variants remain robust to cross-language input (a `zh` run may score
  an English article and vice-versa).
- Each analysis row records the language it was generated in.

**Non-Goals:**
- No post-hoc translation of stored analyses. Content is generated once in the
  request locale; the stored corpus becomes mixed-language by design.
- No localization of user data (`goals.yaml` stays as authored; the locale governs
  output, not the goal definitions).
- No locale filtering of dedup candidates or item selection.
- No reader-side language filter UI in this change (the stored `locale` column
  enables it later; building the filter is out of scope).
- No new supported languages beyond `zh`/`en`.

## Decisions

### D1: Locale = output language only; input stays multilingual

The locale fixes only the generated OUTPUT language. Goals and article content are
input and may be any language. This collapses the mental model: both prompt
variants must handle bilingual input, and differ only in what they emit. It also
makes the "match the language of goals" rule obsolete — each variant hard-asserts
its output language regardless of goals language.

**Alternative considered:** keep goals-language coupling and add locale only as a
tiebreaker. Rejected — it preserves the current confusing behavior and doesn't give
the user deterministic control.

### D2: A2 prompt selection — one config, locale-swapped instructions file

Keep one config per stage (`radar_tier2_impact.yaml`); the loader swaps the
instructions file by locale. Chosen over A1 (separate `_zh`/`_en` configs) because
model profile, tools, and `extra` knobs (`db: false`, `shared_context: false`,
`max_tokens: 4096`) must NOT drift between locales — A2 keeps them single-source
and only forks the prompt text.

**Selection mechanism — suffixed variant with unsuffixed-base fallback:** the
loader resolves the sibling `<stem>.<locale><ext>` first, else the unsuffixed
`<stem><ext>`, else raises. Multi-language agents ship one suffixed file per locale
and **no** unsuffixed base (`radar_tier2_impact.zh.md` + `radar_tier2_impact.en.md`);
single-language agents keep just the unsuffixed base (`knowledge_classifier.md`),
which every locale falls back to. Both languages carry an explicit suffix so the
directory is symmetric (`.zh.md` / `.en.md`) — no "which language is the unmarked
base" ambiguity. `instructions_file` names the logical stem, so a multi-language
agent's YAML still reads `agents/radar_tier2_impact.md` even though only the suffixed
files exist on disk.

Chosen over an explicit YAML mapping field (`instructions_files: {zh:..., en:...}`)
to avoid touching `AgentConfig`'s schema for every agent and to keep unaffected
agents' YAML unchanged; the convention is localized to `resolved_instructions(locale)`.
The suffix is the locale code (`zh`, not `cn`) so the filename derives directly from
`--locale` / `radar_analyses.locale` and pairs with the ISO-639 `en`.

**Alternative considered:** A3 (single prompt + inject "reply in English" at call
time). Rejected by the user requirement for pure-language prompt files — and because
the tier-2 scoring rubric reads and maintains better as one coherent language block
than as a base prompt plus a language-override footnote.

### D3: tier-1 cue vocabulary stays bilingual in both variants

tier-1's drop categories (`会议出席软文`, `厂商 PR 通稿`, `纯行情标题`, etc.) match
real feed text. Because a `zh` run may see English articles and an `en` run may see
Chinese articles, BOTH variants carry cue literals in both languages. Cues are
rendered as **idiomatic equivalents** per language (understand the underlying
meaning, find the phrase that fits that language's media conventions) — NOT literal
translations. Only tier-1's `reason` OUTPUT field switches with locale.

Example mapping (semantic, not literal):

| Chinese cue | Idiomatic English equivalent |
|---|---|
| 厂商 PR 通稿 | vendor launch puff / press-release marketing |
| 会议出席软文 | sponsored speaker / panel-attendance promo |
| 纯行情标题 | bare stock-move / market-cap headline |
| 传闻/leak | unsourced rumor / leak coverage |

### D4: Persist locale per analysis row

Add `radar_analyses.locale TEXT`. The pipeline writes the run locale on every row
(keep and drop). This is provenance for the intentionally mixed-language corpus and
the hook for a future reader badge/filter. Because bootstrap's `CREATE TABLE IF NOT
EXISTS` won't alter an existing table, add the column via `ALTER TABLE ... ADD
COLUMN IF NOT EXISTS locale TEXT` and backfill legacy rows to `'zh'` (historically
everything was Chinese) so the reader never faces a null-language branch.

### D5: dedup stays locale-agnostic

dedup ANN retrieval and the LLM judge do NOT filter by locale. The same event
covered in Chinese and English IS a duplicate, and Qwen3 embeddings are
multilingual, so cross-language dedup is correct and desired. dedup's `reason`
(internal, low-visibility) follows the run locale for consistency. Stored topic
summaries may thus be mixed-language over time — acceptable and expected.

### D6: Single default locale `en` everywhere

Because both languages are now explicitly suffixed (D2), there is no "unmarked base
locale" to anchor, so the earlier split between a base-file anchor and a runtime
default collapses: `paca.core.config.DEFAULT_LOCALE = "en"` is the one system
default. `run()` and CLI `--locale` default to `en`, matching the dashboard's
English-first `DEFAULT_LOCALE = "en"` (set on main), so a bare `paca info-radar
analyze` generates English. `run(locale="zh")` / `--locale zh` still reproduces
Chinese output. For single-language agents the default value is immaterial — any
locale falls back to their unsuffixed base file.

## Risks / Trade-offs

- **Mixed-language radar corpus** → Accepted per non-goal (no post-translation). The
  reader localizes chrome but shows each item's content in its generation language.
  The `locale` column lets a future change label or filter; not solved here.
- **Rubric drift between `_zh` and `_en` tier-2 prompts** (the two-step scoring
  rubric now lives in two files) → Mitigate by keeping the rubric structure
  identical across variants and calling this out in `docs/modules/info_filter.md`; a
  rubric change must land in both files.
- **Cross-language cue coverage regressions in tier-1** → Mitigate with a smoke test
  per locale asserting a known cross-language marketing item is dropped; keep both
  literal sets in both variants.
- **Convention-based prompt resolution is implicit** ("magic" `.en` suffix) → Mitigate
  with the loud-fallback log and a loader unit test covering base, variant, and
  missing-variant resolution.
- **Legacy backfill assumes `zh`** → Any pre-existing rows generated from
  English-language goals would be mislabeled `zh`. Accepted: historically goals were
  Chinese, and `locale` is provenance metadata, not a correctness gate.

## Migration Plan

1. Loader gains `build_from_name(name, locale)` + `resolved_instructions(locale)`
   resolving `<stem>.<locale><ext>` first, then unsuffixed base, else raise.
2. Author the 6 pure-language prompt files as suffixed `.zh.md` / `.en.md` pairs
   (the old unsuffixed `radar_*.md` are renamed to `.zh.md`), with bilingual
   idiomatic tier-1 cues.
3. Thread locale: `runner.run(locale=)` → stages → agent build.
4. CLI `--locale` (default `en`); dashboard forwards `paca_locale` into the spawn.
5. Schema: `ALTER TABLE radar_analyses ADD COLUMN IF NOT EXISTS locale TEXT`,
   backfill `'zh'`; `insert_analysis(locale=)`; runner passes it.
6. Docs + tests.

**Rollback:** reverting the code restores goals-language behavior; the `locale`
column can be left in place (unused) or dropped — no data loss either way since it
is provenance metadata.

## Open Questions

- Should the reader surface a language badge on cards in THIS change, or defer the
  entire reader-side treatment to a follow-on? (Proposal currently defers; the
  column is written regardless.)
- Is `en` output over Chinese `goals.yaml` good enough with on-the-fly concept
  translation, or do we eventually want an English `goals.yaml` variant too? (Out of
  scope here — goals are user data, not prompts.)
