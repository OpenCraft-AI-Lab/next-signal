## 1. Loader: locale-aware prompt selection

- [x] 1.1 Add `locale` param to `AgentConfig.resolved_instructions(locale)` in `src/paca/core/config.py` (default `DEFAULT_LOCALE = "en"`): resolve the sibling `<stem>.<locale><ext>` variant first; else fall back to the unsuffixed `<stem><ext>` base (single-language agents); else raise `FileNotFoundError`.
- [x] 1.2 Thread locale through `src/paca/agents/loader.py`: `build_from_name(name, locale="zh")` → `build_from_config(cfg, locale)` → `_compose_instructions(cfg, locale)` → `cfg.resolved_instructions(locale)`. Default keeps current behavior.
- [x] 1.3 Add `tests/test_agent_loader_locale.py`: base resolution, `.en` variant resolution, and missing-variant fallback (asserts base text + a logged fallback), using a temp prompt fixture.

## 2. Prompts: de-mix into pure-language variants

- [x] 2.1 `radar_tier2_impact`: author `prompts/agents/radar_tier2_impact.zh.md` as pure Chinese (prose + two-step rubric + hard ceilings) and `radar_tier2_impact.en.md` as pure English with the same rubric structure. Remove the "match the language of goals" rule; each variant hard-asserts its output language. (Both suffixed; no unsuffixed base.)
- [x] 2.2 `radar_tier1_filter`: author `prompts/agents/radar_tier1_filter.zh.md` (zh) and `radar_tier1_filter.en.md` (en). Keep the drop-category **cue vocabulary bilingual in both** — carry Chinese and English cue literals as idiomatic per-language equivalents (see design §D3 table), not literal translations. Only the `reason` output language switches.
- [x] 2.3 `radar_dedup_judge`: author `prompts/agents/radar_dedup_judge.zh.md` (zh) and `radar_dedup_judge.en.md` (en). Replace "match the language of the input summaries" with a fixed output language per variant.

## 3. Pipeline: thread locale end-to-end

- [x] 3.1 `runner.run(*, limit, source, locale="en")` in `src/paca/workflows/info_radar_analysis/runner.py`: accept locale (runtime default `en`) and pass it into `_run_chunk` / `_process_item` and onward to each stage.
- [x] 3.2 `stages/tier1.py`: add `locale` param to `run` / `run_batch`; build via `build_from_name("radar_tier1_filter", locale)`.
- [x] 3.3 `stages/tier2.py`: add `locale` param to `run`; build via `build_from_name("radar_tier2_impact", locale)`.
- [x] 3.4 `stages/dedup.py`: add `locale` param to `run`; build via `build_from_name("radar_dedup_judge", locale)` (candidate retrieval stays locale-agnostic).

## 4. Persist locale on analysis rows

- [x] 4.1 `scripts/bootstrap_db.py`: add `locale TEXT` to the `radar_analyses` CREATE block, plus an idempotent `ALTER TABLE radar_analyses ADD COLUMN IF NOT EXISTS locale TEXT` and a one-time backfill of NULL → `'zh'`.
- [x] 4.2 `store.py::insert_analysis`: add `locale: str` param and include it in the INSERT column list / VALUES.
- [x] 4.3 `runner._process_item`: pass the run `locale` into every `insert_analysis` call (drop, novel, duplicate paths).

## 5. CLI surface

- [x] 5.1 `src/paca/interfaces/cli.py::info_radar_analyze`: add `--locale` option (`zh`|`en`, default `en`), validate the value, and pass `locale=` into `run_analysis(...)`.

## 6. Dashboard: forward UI locale

- [x] 6.1 `dashboard/lib/actions/radar.ts`: `spawnAnalyzeTracked(locale)` appends `--locale <locale>` to the analyze argv; `runPullAndAnalyze(localeValue)` normalizes `paca_locale` and passes it through.

## 7. Docs

- [x] 7.1 `docs/modules/info_filter.md`: update invariants — output language is driven by request locale (not goals language); note the `radar_analyses.locale` column, the pure-language prompt variants, and that the tier-2 rubric now lives in two files that must stay in sync.

## 8. Verification

- [x] 8.1 `uv run pytest -q` green (loader locale tests + existing suite): 308 passed, 9 skipped. Also verified the real `radar_*` configs resolve distinct `zh`/`en` prompt files, and ruff clean on all changed files.
- [ ] 8.2 Containerized end-to-end per CLAUDE.md: `docker compose build`; run `paca info-radar analyze --locale en --limit N` and confirm persisted `radar_analyses` rows have English `summary`/`impact_md` and `locale='en'`; run `--locale zh` and confirm Chinese output with `locale='zh'`. **Deferred — needs Docker + live OMLX endpoint + Postgres, not available in this session.**
- [ ] 8.3 Cross-language cue smoke: confirm a Chinese vendor-PR item is dropped under `--locale en` (bilingual tier-1 cues) with an English `reason`. **Deferred — needs a live LLM run (see 8.2).**
- [ ] 8.4 Dashboard: with UI set to English, `Pull + Analyze` spawns `... analyze --locale en` and produces English analyses. **Deferred — needs Docker stack (see 8.2); dashboard TS typecheck also needs `npm install`.**

## 9. Reader-facing localized title (`display_title`)

- [x] 9.1 `src/paca/workflows/info_radar_analysis/schemas.py`: add `display_title: str` to `Tier2Analysis` (Field description: "concise reader-facing headline in the run locale, distinct from `summary`").
- [x] 9.2 `prompts/agents/radar_tier2_impact.zh.md` and `.en.md`: add the `display_title` field instruction — a concise headline in each variant's language — keeping the two variants structurally identical (JSON schema block + `## Fields` entry + style rule).
- [x] 9.3 `scripts/bootstrap_db.py`: add `display_title TEXT` to the `radar_analyses` CREATE block and an idempotent `ALTER TABLE radar_analyses ADD COLUMN IF NOT EXISTS display_title TEXT` (no backfill), executed in `main()`.
- [x] 9.4 `store.py::insert_analysis`: add `display_title: str | None = None` and include it in the INSERT; `runner._process_item` passes the tier-2 `display_title` on both keep paths (drop rows leave it null).
- [x] 9.5 `dashboard/lib/radar/queries.ts`: select `display_title` in `getItemsForDay` / `getItemDetail` / `getDayGroups` (top_items + coalesced top_title) and coalesce it in `getFilteredTodayList`; add it to `RadarItem` / `DayGroupTopItem` / row types + `normalizeItem`.
- [x] 9.6 `dashboard/components/radar/signal-card.tsx` (today list), `day-group.tsx` (past days), and the `/radar` export appendix: render `item.displayTitle ?? item.title`. Detail pager uses the coalesced list title (no code change).
- [x] 9.7 `dashboard/app/radar/[id]/page.tsx`: use `displayTitle ?? title` as the heading and show the original `title` as a secondary "original title" line when it differs (new `t.radar.detail.originalTitle` label, zh+en); the unanalyzed placeholder still falls back to the feed title.
- [x] 9.8 `docs/modules/info_filter.md` + `docs/zh/modules/info_filter.md`: note `display_title` is generated content in the run locale (persisted on `radar_analyses`), the feed `radar_items.title` is preserved, and both tier-2 prompt variants carry the field in sync.
- [x] 9.9 Verify (runnable): `uv run pytest -q` green — 345 passed, 13 skipped, incl. the new tier-2 prompt-variant test and a runner assertion that the keep-path `insert_analysis` carries `display_title`; ruff clean on all changed Python. **Containerized + dashboard visual deferred** — needs Docker + OMLX + Postgres + `npm install` (same environment gap as 8.2–8.4): `--locale zh/en` display_title round-trip, `/radar` card + detail rendering with feed-title fallback and preserved original title.
