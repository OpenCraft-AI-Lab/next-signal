## Why

The scheduler misreports its own state in two ways, and on 2026-08-10 both showed up in one morning.

`catch_up` is consulted only on the poll loop's first tick. A laptop that sleeps through 08:00 and wakes at 09:30 never restarts the process, so the missed slot fires regardless of `catch_up: false` — the exact case the setting exists to prevent, and the exact case `core-schedule` already promises to honour in its "host suspend is not a special case" scenario.

Separately, a run's outcome is written only when the whole chain finishes. That morning's run took 80 minutes, so the settings page showed the *previous* run's status for its entire duration and then flipped to "just now" at the end. The operator read that as the scheduler catching up a missed run; it took a cross-referenced dig through container and OMLX server logs to establish that the run had in fact started on time. A run that can last 80 minutes needs to say so while it is happening.

## What Changes

- Replace the `first_tick` special case in `tick()` with a single question — did this slot come due within *twice* the poll interval? On time fires; later than that is a missed run, and `catch_up` decides. The window is doubled as grace: one interval is when a slot is normally noticed and the second absorbs a poll made slow by its own database reads, while every real miss is minutes to days late. One rule now covers process restart, container restart, and host suspend/resume, and the `first_tick` parameter disappears.
- **BREAKING** (behavioural, for operators running with `catch_up: false`): a slot that comes due while a previous run is still executing counts as missed and is skipped. Today it fires back-to-back the moment the previous run returns. With runs measured at up to 80 minutes, stacking is the worse outcome.
- Record a run as in progress before the chain starts, not only when it ends, and reconcile a run that was interrupted rather than leaving it in progress forever.
- Write that in-progress record in the **same statement** that consumes the slot, so no crash window can leave a slot advanced with no run on record — a state reconciliation cannot see and the panel cannot show, in which the day's run is simply skipped in silence.
- Show the in-progress state in the settings page's schedule section, with elapsed time, in both UI locales.
- Stop offering a timezone control the scheduler does not read. The zone is `INFO_RADAR_TIMEZONE`, shared with radar day grouping and review due dates; the section states it read-only instead of storing a second, inert copy whose only effect was a warning that it had no effect.
- Reject a non-boolean `enabled` / `catch_up` in `schedule.json` instead of coercing it. `bool("false")` is `True`, and this file is hand-editable by design, so the coercion could leave the scheduler on when the operator had switched it off — on the one path that spends model tokens unattended.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-schedule`: the seeding rules stop being anchored to process start — `catch_up` governs every missed slot, however the miss happened. A second requirement is added for recording a run's start and reconciling an interrupted one.
- `dashboard-shell`: the schedule section's read-back gains a fourth state — in progress — alongside never-run, succeeded, and failed.

## Impact

- `src/next_signal/orchestrator/schedule.py` — `tick()` loses `first_tick` and gains a lateness comparison; a new `claim_slot()` consumes the slot and records the start in one statement, leaving `write_slot()` for seeding alone; `run()` reconciles a stale in-progress row at startup.
- `src/next_signal/core/schedule.py` — `enabled` and `catch_up` are read through a strict boolean check rather than `bool()`.
- `dashboard/components/settings/schedule-section.tsx` and `dashboard/lib/i18n/dictionaries.ts` — the new read-back state and its en/zh strings, and the timezone select replaced by a stated value. `dashboard/lib/actions/schedule.ts` already returned `lastStatus` and `lastRunAt`, but is **not** unchanged: it gains the reader that admits `running` as an ordinary value rather than discarding it as absent, and drops the `tz` field and its validator.
- `dashboard/app/globals.css` — one class for a setting the environment decides, shown where its control would sit.
- `tests/test_scheduler.py` — the seeding tests are written around `first_tick` and are rewritten against the lateness rule; the interrupted-run reconciliation and the slot/start pairing each need their own case. `tests/test_schedule_config.py` — the strict boolean check.
- No DDL. `schedule_state.last_status` is already `TEXT` with no constraint, and `last_run_at` carries the start time until the outcome overwrites it.
- **Archive ordering**: both capabilities' requirements currently live in the unarchived `wall-clock-scheduler` change's deltas, not in `openspec/specs/`. This change's deltas modify requirement names that only exist there, so `wall-clock-scheduler` (with `add-coding-agent-cli-bridge`, which must be archived alongside it) has to be archived before this one.
