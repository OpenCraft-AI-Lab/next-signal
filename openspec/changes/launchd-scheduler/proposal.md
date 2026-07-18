## Why

Scheduled jobs (e.g. daily portfolio brief at 08:30) need to survive Mac sleep — if the wake time is missed, the job must run on next wake. agno's in-process scheduler does not handle sleep; macOS `launchd` with `StartCalendarInterval` does.

## What Changes

- Implement a launchd-based scheduler: one launchd plist per job calls a single dispatcher, which POSTs to AgentOS and records the run in `job_runs`.
- Add `paca schedule install / list / remove / run-now` CLI to manage launchd plists from the YAML config.
- Sync `configs/schedules.yaml` into the `scheduled_jobs` table so the dashboard can read the registry.
- Register the `daily_portfolio_brief` workflow as the first scheduled job.

## Capabilities

### New Capabilities

- `launchd-scheduler`: launchd-driven dispatcher + CLI for installing/listing/removing scheduled jobs, with sleep-safe catch-up behavior.

### Modified Capabilities

- `core-cli`: adds `paca schedule …` subcommand group.
- `core-database`: adds the `job_runs` and `scheduled_jobs` business tables (schema already in `bootstrap_db.py`).

## Impact

- Code: `src/paca/scheduler/{runs,dispatcher,plist}.py`, `src/paca/workflows/daily_portfolio_brief.py`, CLI subcommand.
- Configs: `configs/schedules.yaml`, `configs/workflows/daily_portfolio_brief.yaml`.
- System: writes plists under `~/Library/LaunchAgents/`.
