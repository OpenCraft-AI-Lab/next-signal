## Why

Radar analysis output (summary / impact / tier-1 reason) is written in whatever
language `configs/info_radar/goals.yaml` happens to be in — every analysis prompt
ends with "match the language of `goals`". Switching the dashboard between 中文 and
English localizes only the chrome; the LLM-generated content never changes
language. The locale the user picked already reaches the analyze server action but
is dropped before it reaches the pipeline. Users want the generated content itself
to follow the UI language.

## What Changes

- Output language of radar analysis is driven by the **request locale**, not by the
  goals-block language. **BREAKING** (behavioral): Chinese goals under an English
  locale now yield English `summary`/`impact`; today they yield Chinese.
- The UI locale threads end-to-end: dashboard analyze spawn → `paca info-radar
  analyze --locale <zh|en>` → `runner.run(locale=)` → each stage → agent build.
- Agent construction becomes locale-aware: `build_from_name(name, locale)` selects a
  per-locale prompt file for the same single config (model / tools / `extra` stay
  single-source). Resolution prefers the `<stem>.<locale>.md` variant and falls back
  to an unsuffixed base for single-language agents.
- Each analysis prompt is de-mixed into **pure-language variants**, both explicitly
  suffixed: the current EN/CN-mixed `radar_tier1_filter` / `radar_tier2_impact` /
  `radar_dedup_judge` prompts split into a `.zh.md` file (pure Chinese prose +
  rubric) and a `.en.md` file (pure English prose + rubric), with no unsuffixed base.
- tier-1 drop-category **cue vocabulary stays bilingual in both variants** — a
  Chinese run may score an English article and vice-versa. Cues are rendered as
  idiomatic equivalents per language (semantic match, not literal translation), and
  each variant keeps both-language literals so real feed text is still recognized.
- `radar_analyses` gains a `locale` column recording the generation language of each
  row (provenance for the mixed-language corpus; enables a future reader
  badge/filter). Legacy rows backfill to `zh`.
- No post-translation: content is generated once in the request locale and stored as
  is. The stored corpus becomes mixed-language by design.

## Capabilities

### New Capabilities
<!-- none — this modifies existing capabilities -->

### Modified Capabilities
- `info-radar-analysis`: output language is selected by request locale rather than
  goals-block language; pipeline threads a locale and persists it per analysis row;
  prompts split into pure-language variants with bilingual tier-1 cue vocabulary.
- `core-agents`: agent construction accepts a locale that swaps the resolved
  instructions file for the same config, resolving a suffixed `<stem>.<locale>.md`
  variant and falling back to the unsuffixed base for single-language agents.
- `core-cli`: `paca info-radar analyze` accepts `--locale <zh|en>` (default `en`).
- `dashboard-radar-reader`: the Pull + Analyze action forwards the active UI locale
  to the analyzer so generated content matches the dashboard language.

## Impact

- **Prompts**: `prompts/agents/radar_tier1_filter`, `radar_tier2_impact`,
  `radar_dedup_judge` → de-mixed, explicitly-suffixed `.zh.md` + `.en.md` variants
  (6 files; no unsuffixed base).
- **Loader**: `src/paca/agents/loader.py` (`build_from_name`, `_compose_instructions`);
  `src/paca/core/config.py` (`AgentConfig.resolved_instructions`).
- **Pipeline**: `src/paca/workflows/info_radar_analysis/runner.py` and
  `stages/{tier1,tier2,dedup}.py` (locale param); `store.py`
  (`insert_analysis` locale).
- **CLI**: `src/paca/interfaces/cli.py` (`info-radar analyze --locale`).
- **Dashboard**: `dashboard/lib/actions/radar.ts` (`runPullAndAnalyze` forwards locale
  to the analyze spawn).
- **Schema**: `scripts/bootstrap_db.py` (`radar_analyses.locale` via
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, backfill `zh`).
- **Docs**: `docs/modules/info_filter.md` invariants (output language = request
  locale; new column).
- No new dependencies. dedup candidate retrieval stays locale-agnostic
  (cross-language dedup is intended; embeddings are multilingual).
