## Why

Every info-radar run today is manual: an operator has to remember to run
`next-signal info-radar pull` and then `next-signal info-radar analyze`, or click
through the dashboard. A radar that only fires when someone remembers it is not a
radar. The pipeline is already safe to run unattended — `radar_items.seen_at`
makes `analyze` idempotent at any cadence — so what is missing is only the trigger.

Host schedulers (cron / launchd / Windows Task Scheduler) would mean three
implementations, three sets of docs, and three failure modes for a stack that
already ships as one Docker Compose deployment on all three platforms. Scheduling
inside the container is written once and behaves identically everywhere.

## What Changes

- A new always-on `scheduler` container service runs a poll loop that fires the
  radar chain (`info_radar_pull` → `info_radar_analysis`) at a configured
  wall-clock time.
- A new `next-signal schedule` CLI command runs that loop (this is the service's
  command).
- Schedule configuration is a user-editable state file,
  `~/.next-signal/schedule.json`, holding `enabled`, `at` (`HH:MM`), and
  `catch_up`. An absent file means "never configured", which reads as disabled.
- A new `schedule_state` business table records, per job, the last calendar slot
  already handled plus the last run's timestamp, status, and error.
- Settings move out of the nav popover onto a `/settings` page, and gain a
  section for the schedule: on/off, the daily times, the timezone they are
  recorded in, whether to catch up a run missed while the machine was down, and
  a read-back of the last run. Four sections do not fit an anchored panel, so
  the gear becomes a link and the `Popover` primitive is retired with it.
- `radar_timezone()` moves from two duplicated workflow `store.py` copies into
  `next_signal.core`, since the scheduler is its third consumer.
- Docs and specs that currently assert "there is no background scheduler" are
  corrected.

Deliberately **not** in scope: cron expressions (the config is a wall-clock time,
not an interval or weekday filter), multiple jobs, retries, a run-history view,
and a "run now" button — the dashboard already has per-pipeline manual triggers.

## Capabilities

### New Capabilities

- `core-schedule`: unattended wall-clock triggering of workflow chains — the
  schedule state file and its semantics, the slot-based missed-run model, the
  catch-up policy, and the scheduler service's runtime behavior.

### Modified Capabilities

- `core-cli`: adds a `next-signal schedule` command that runs the scheduler loop
  in the foreground.
- `core-database`: adds `schedule_state` to the business tables provisioned by
  `scripts/bootstrap_db.py` and to the set that uses the bare-`psycopg` path.
- `dashboard-shell`: the nav settings panel that owns exactly one setting
  (content language) becomes a `/settings` page — the requirement is renamed
  accordingly — and gains an independent section for the schedule, including the
  last-run read-back. The app shell drops its host chip and its last piece of
  client-resolved state along with the panel.
- `knowledge-reindex`: its statement that "there is no background scheduler" is
  now false as a global claim. The re-index workflow itself stays manual-only, so
  the requirement is narrowed to say that rather than deleted.

## Impact

**New code**

- `src/next_signal/core/clock.py` — `radar_timezone()` / `now_local()`
- `src/next_signal/core/schedule.py` — read/validate the state file
- `src/next_signal/orchestrator/schedule.py` — the poll loop and `schedule_state` SQL
- `src/next_signal/orchestrator/run_now.py` — `_run_workflow_now` lifted out of the CLI so the loop and the CLI share it
- `dashboard/lib/actions/schedule.ts` — server actions for the state file and status read

**Modified**

- `src/next_signal/interfaces/cli.py` — new `schedule` command; `run-workflow` docstring no longer claims there is no scheduler
- `src/next_signal/workflows/info_radar_recap/store.py`, `src/next_signal/workflows/knowledge_review/store.py` — import `radar_timezone` from core instead of each defining it
- `scripts/bootstrap_db.py`, `src/next_signal/core/db.py` — `schedule_state` DDL and contract registration
- `docker-compose.yml` — `scheduler` service
- `dashboard/lib/paths.ts`, `dashboard/lib/i18n/dictionaries.ts`, `dashboard/components/nav.tsx`; `dashboard/components/settings-panel.tsx` and `components/ui/popover.tsx` are replaced by `dashboard/app/settings/page.tsx` + `dashboard/components/settings/`

**Dependencies**: none added. Wall-clock slot arithmetic uses `datetime` +
`zoneinfo`; the dashboard reuses the existing `pg` pool, `Segmented`, `Input`,
and `relative-time` helpers, so no new UI primitive and no `/design` entry.

**Docs**: `docs/operations.md`, `docs/modules/info_filter.md`,
`docs/containerized-deployment.md`, `dashboard/README.md`, plus the `docs/zh/`
and `README.zh-CN.md` mirrors — all bilingual pairs updated in this change.

**Operational**: the scheduler cannot fire while the container host is not
running Docker. That limit is unchanged by this change and is exactly what the
`catch_up` option exists to soften.
