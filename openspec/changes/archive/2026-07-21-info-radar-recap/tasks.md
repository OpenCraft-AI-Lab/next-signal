## 1. Database

- [x] 1.1 Add `CREATE_RADAR_RECAPS` DDL to `scripts/bootstrap_db.py` with the documented columns and `UNIQUE (since, until, min_score, novel_only)`, no FK to `radar_items`; wire it into `main()` alongside the existing table creates
- [x] 1.2 Verify idempotence: run bootstrap twice against a database that already holds recap rows and confirm rows survive — confirmed against the live Postgres container (`CREATE TABLE IF NOT EXISTS` re-run skipped, row count preserved)

## 2. Agent

- [x] 2.1 Write `configs/agents/radar_recap.yaml` — `model_profile: local_structured`, `tools: []`, `extra: {db: false, shared_context: false}`, no `max_tokens` override
- [x] 2.2 Write `prompts/agents/radar_recap.md` — instruct 3–5 themes, one narrative paragraph each, cite by item id, synthesize across items rather than restating them individually

## 3. Workflow

- [x] 3.1 Create `src/paca/workflows/info_radar_recap/store.py`: candidate selection (range in radar tz, `verdict='keep'`, score/novel gate, top-60 by score, returns rows plus `considered_count`), recap upsert, and recap read-by-key
- [x] 3.2 Create `src/paca/workflows/info_radar_recap/__init__.py`: `RecapOutput` / `Theme` pydantic schemas, `factory`, and `run()` driving validate-range → select → short-circuit-if-empty → mark running → `build_from_name("radar_recap")` + `run_structured` → validate citations → persist
- [x] 3.3 Implement citation validation: drop ids not in the input set (log a warning), drop themes left uncited, and raise to the `status='error'` path when no theme survives
- [x] 3.4 Implement the status lifecycle: write `running` before the LLM call, preserve prior `headline`/`themes` across a regeneration, set `done` or `error` on completion, and no-op when the key is already `running`
- [x] 3.5 Write `configs/workflows/info_radar_recap.yaml` — `expose.agent_os: false`, `expose.tool.enabled: false`, `extra.run_now` pointing at the module entrypoint

## 4. CLI

- [x] 4.1 Add `paca info-radar recap --since --until [--min-score] [--novel-only] [--regenerate]` to `src/paca/interfaces/cli.py`, printing headline plus one line per theme with citation count
- [x] 4.2 Handle the non-happy paths: inverted/unparseable range exits non-zero before any agent call; empty range prints an explicit message and exits zero; cached `done` recap prints without an LLM call unless `--regenerate`

## 5. Dashboard — data layer

- [x] 5.1 Create `dashboard/lib/radar/recap.ts`: read a recap by `(since, until, minScore, novelOnly)` via direct Postgres, and compute staleness by comparing stored `max_analyzed_at` / `item_count` against a live count over the same range and gate
- [x] 5.2 Add a server action that triggers generation through `spawnPacaDetached` and returns immediately, mirroring the existing Pull + Analyze launcher

## 6. Dashboard — UI

- [x] 6.1 Build the range selector (last 7 days / last 30 days / custom from–to) writing the range into the URL query string, resolving presets in the radar timezone
- [x] 6.2 Build the recap panel: headline, per-theme title + narrative, citation links to detail pages, plain text for citations whose item was swept, and a coverage line when `considered_count > item_count`
- [x] 6.3 Wire poll-by-status: `running` in-progress state, `done` renders, `error` surfaces the message and stops polling while still showing any prior content
- [x] 6.4 Add the staleness marker beside the regenerate control; confirm no auto-regeneration fires on load
- [x] 6.5 Suppress all recap chrome under `?export=1`
- [x] 6.6 Add EN + ZH strings to `dashboard/lib/i18n/dictionaries.ts`, English canonical; verify the panel in both locales
- [x] 6.7 Place the recap section above the filter bar's "today's high-signal items" heading (recap is a synthesis over the items, not one of them)
- [x] 6.8 Browse saved recaps: `listRecaps()` in `dashboard/lib/radar/recap.ts` + a `SavedRecaps` list in the past-days area, each row linking back to `#recap` with the stored range and gate (reuses `.card`/`.pastrow`/`.elip`, no new design-system class); EN + ZH strings
- [x] 6.9 Rename the section to "Smart Recap" (EN) / "智能回顾" (ZH) and make it collapsible (`SmartRecapSection` on the Radix Collapsible primitive), persisting the choice in a `paca_recap_collapsed` cookie so a filter-change re-render keeps it; force-open when the URL targets a specific recap

## 7. Tests

- [x] 7.1 Range and gate selection: inclusive bounds in the radar timezone, inverted range raises, `drop` verdicts excluded, novel-only excludes duplicates
- [x] 7.2 Top-60 cap: `item_count` / `considered_count` recorded correctly both when capped and when under the cap
- [x] 7.3 Citation validation: unknown id dropped, uncited theme dropped, all-invalid raises to the error path
- [x] 7.4 Cache and lifecycle: repeat request makes no LLM call, regeneration upserts in place, failed regeneration preserves prior content, `running` key no-ops
- [x] 7.5 Payload shape: assert `impact_md` is absent from the serialized agent input
- [x] 7.6 Empty range writes no row and makes no agent call

## 8. Docs

- [x] 8.1 Document the recap layer in `docs/modules/info_filter.md` — agent, workflow, `radar_recaps`, cache key, staleness semantics — and update its 规范与状态 section
- [x] 8.2 Mirror into `docs/zh/modules/info_filter.md`, keeping structure one-to-one with the English page
- [x] 8.3 Sync the other docs that enumerate what changed: `docs/modules/core.md` (business-table list) and `docs/modules/dashboard.md` (page table + api route count), both locales. `docs/architecture.md` needed no change — its table mentions sit inside a collector→analysis pattern description that recap is not an instance of, and its workflow enumeration is scoped to analysis workflows

## 9. Verification

- [x] 9.1 `uv run pytest -q` green (324 passed, 9 skipped); `uv run ruff check src scripts tests` clean; dashboard `npm run typecheck` + `npm run lint` clean
- [x] 9.1a SQL verified directly against the live Postgres container (the part unit tests can't cover): DDL + idempotence, full status lifecycle (claim / running no-op / finish / regenerate-preserves-content / fail-preserves-content), separate row per quality gate, and `select_candidates` — confirmed `count(*) OVER ()` reports the full match count (36) under `LIMIT 3`, and `EXPLAIN VERBOSE` shows no `impact_md` in the projected output
- [x] 9.2 End-to-end in Docker (the Docker Hub blip cleared — registry reachable again, rebuilt clean): `docker compose build` + `docker compose up -d --force-recreate` on the fresh image. Container bootstrap provisioned `radar_recaps` (exit 0). `docker compose exec dashboard paca info-radar recap --since 2026-07-18 --until 2026-07-18` generated a real recap via OMLX (4 themes, 20 citations); the persisted row is `status=done, item_count=36, considered_count=36`; a repeat call printed `(cached)` with no HTTP request (cache hit). The `/radar` panel renders the headline, all four themes with narratives, and citation chips linking to detail pages. Note: 2026-07-19 UTC analyses bucket to local day 2026-07-18 in the radar tz — the range is `analyzed_at` in local time, as specified
- [x] 9.3 Recap agent output fit the inherited 4096 cap in the real run — full headline + four complete themes, no truncation, no widening of `local_structured`
