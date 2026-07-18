## Why

We currently have no first-class way to pull "what's new" from RSS-style and text-platform sources into local storage on a schedule. Existing knowledge ingest is on-demand and agent-driven; financial news is one-domain-specific. We need a generic, low-overhead collector so a future analysis workflow has a fresh, deduped pool of items to reason over.

## What Changes

- New collector module `paca/collectors/info_radar/` that periodically invokes CLI-based sources (no LLM in the loop) and writes results to a Postgres table.
- New Postgres business table `radar_items` with a `(source, source_id)` unique constraint for source-level dedup and a 30-day retention window.
- First source wired end-to-end: a Folo timeline source (via `folocli`). Architecture supports multiple sources from day one (YAML descriptor + parser registry); additional sources are out of v1 scope.
- New `paca info-radar pull [--source NAME]` and `paca info-radar sweep` CLI subcommands.
- New thin `paca/workflows/info_radar_pull.py` shell so the existing scheduler can fire the collector without scheduler-schema changes.
- `configs/info_radar/sources.yaml` declares source descriptors (CLI argv, timeout, parser name); parsers live in a registry under `paca/collectors/info_radar/parsers/`.
- `paca doctor` gains folocli/opencli health checks; `.env.example` gains `FOLO_TOKEN`.

Non-goals (deferred to future changes): downstream analysis workflow, dashboard page, Discord notifications, incremental `--cursor` pull optimization, cross-source dedup, content hashing, additional sources beyond Folo (e.g., opencli adapters — Chrome-bridge architecture turned out heavier than expected for v1).

## Capabilities

### New Capabilities
- `info-radar`: CLI-driven periodic collector that pulls items from RSS-style and text-platform sources, dedups per source, persists to Postgres, and retains for 30 days.

### Modified Capabilities
- `core-cli`: adds `paca info-radar pull` and `paca info-radar sweep` subcommands, plus folocli/opencli checks inside `paca doctor`.
- `core-database`: adds `radar_items` to the list of business tables managed via raw psycopg.

## Impact

- **New code**: `paca/collectors/info_radar/` (runner, store, schema, parsers), `paca/integrations/info_radar/folo.py` (CLI argv helpers if any), `paca/workflows/info_radar_pull.py` (scheduler shell), CLI subcommand registration.
- **New config**: `configs/info_radar/sources.yaml`, `configs/schedules.yaml` gets one `info_radar_pull` entry.
- **DDL**: `scripts/bootstrap_db.py` adds the `radar_items` table.
- **Env**: `.env.example` adds `FOLO_TOKEN`; optional `FOLO_CLI_ARGV` for operator override.
- **External dependencies**: `folocli` (run via `npx`, no global install required).
- **No breaking changes** to existing capabilities; all additions are additive.
