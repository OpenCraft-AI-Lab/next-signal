## Why

The radar reader is built around a single day: `/radar` shows today's kept items, and past days collapse into per-day count/median rows. Nothing answers "what actually happened this week" — at a typical keep rate that means re-reading 40+ cards and doing the synthesis by hand. The analysis pipeline already produces per-item `summary` / `impact_md` / `score` / `tags`; a recap is the missing layer that turns a range of those into the few themes that actually moved.

## What Changes

- New **recap workflow**: given a time range, select the kept analyses that clear the quality bar, group them into 3–5 themes, and emit one narrative paragraph per theme with citations back to the contributing `radar_items` ids. Output is themed synthesis, not a per-item list — a recap that merely regroups bullets is the existing export in a different shape.
- New **`radar_recaps` business table** caching one row per recap request key. Re-opening a range served from cache costs nothing; regeneration is explicit and operator-triggered. Local-model synthesis over a week's items is a 30–60s job, so caching is what makes the panel usable rather than a nice-to-have.
- New **`radar_recap` agent** (`configs/agents/` + `prompts/agents/`) on the `local_structured` profile with `extra: {db: false, shared_context: false}` — a pure transform with no session history, matching the three existing analysis agents.
- New **`paca info-radar recap`** CLI subcommand, the manual entrypoint and the thing the dashboard spawns.
- **`/radar` gains a range selector + recap panel.** Generation follows the established fire-and-forget shape: `spawnPacaDetached` then poll for the persisted result, exactly as `Pull + Analyze` already does, because the dashboard cannot hold a request open for a minute of local inference.
- Bilingual docs, English canonical.

Non-goals: no change to the two-tier analysis pipeline or its outputs; no scheduled/automatic recaps (manual trigger only); no new push or notification surface.

## Capabilities

### New Capabilities

- `info-radar-recap`: range-scoped synthesis over `radar_analyses` — selection window, quality gate, theme clustering with citations, cache-key semantics and regeneration, and the failure isolation rules for the LLM step.

### Modified Capabilities

- `core-cli`: adds a `paca info-radar recap` requirement alongside the existing `pull` / `sweep` / `analyze` / `subscriptions` subcommand requirements.
- `core-database`: adds a `radar_recaps` provisioning requirement, and extends the raw-psycopg requirement's business-table list (currently `radar_items`, `radar_analyses`, `radar_pushed_topics`) to include it.
- `dashboard-radar-reader`: adds the range selector and recap panel to the radar index page, including the trigger + poll behavior and the cached-vs-stale presentation.

## Impact

**New files**: `src/paca/workflows/info_radar_recap.py` (+ store/schema helpers), `configs/workflows/info_radar_recap.yaml`, `configs/agents/radar_recap.yaml`, `prompts/agents/radar_recap.md`, dashboard recap components + query module, tests.

**Modified**: `scripts/bootstrap_db.py` (DDL), `src/paca/interfaces/cli.py` (subcommand), `dashboard/app/radar/page.tsx`, `dashboard/lib/i18n/dictionaries.ts` (EN + ZH strings), `docs/modules/info_filter.md` + `docs/zh/modules/info_filter.md`.

**Data**: one new table. No migration of existing rows; `radar_recaps` references `radar_items` only by id inside a JSONB citation payload, so it is unaffected by the 30-day sweep except that citations to swept items become dangling — recaps are point-in-time artifacts and are expected to outlive their sources.

**Cost**: one LLM call per uncached (range, quality-gate) pair. No additional load on the per-item analysis path.
