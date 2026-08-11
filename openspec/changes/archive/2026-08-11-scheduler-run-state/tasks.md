## 1. Missed-run policy

- [x] 1.1 Replace `tick()`'s `first_tick` parameter with `tick_seconds`, and seed on a late slot when `catch_up` is false: a due slot is on time when `now - prev_slot <= 2 * tick_seconds`, late otherwise (design D1). Keep the effective-schedule and missing-row seeding rules exactly as they are.
- [x] 1.2 Update `run()` to pass its poll interval into `tick()` and drop the `first_tick` bookkeeping. Keep `prev_slot` in `core.schedule` untouched — lateness is loop policy, not slot arithmetic (design D2).
- [x] 1.3 Update the docstrings in `src/next_signal/orchestrator/schedule.py` that still describe seeding in terms of process start, including the module docstring's "a suspended VM is just an unusually long tick" line, which is now only half the story: the tick is long *and* the slot it finds is late.

## 2. Run-state recording

- [x] 2.1 Rename `write_outcome` to `write_run_state(job, *, status, error)` and use it for all three writes (design D3). Update the call sites and `tests/test_scheduler.py`.
- [x] 2.2 Write `running` at the top of `fire()`, before the first workflow, once per chain rather than once per leg.
- [x] 2.3 Reconcile at startup: in `run()`, before the poll loop, rewrite a row whose `last_status` is `running` to `failed`, keeping `last_run_at` and recording an error line naming the cause (design D4, D5). Leave `ok` / `failed` / absent rows alone.

## 3. Dashboard read-back

- [x] 3.1 Add a `running` branch to `lastRun()` in `dashboard/components/settings/schedule-section.tsx`, rendering the in-progress line with elapsed time from the existing `timeAgo` helper against `lastRunAt`. Route every other non-`ok` status through the existing failure branch (design D5).
- [x] 3.2 Add the `scheduleRunning` entry to both `en` and `zh` dictionaries in `dashboard/lib/i18n/dictionaries.ts`. No new UI primitive, so no `/design` catalogue addition.
- [x] 3.3 Widen the status plumbing in `dashboard/lib/actions/schedule.ts`: `ScheduleStatus.lastStatus` is typed `"ok" | "failed" | null` and `getScheduleStatus()` maps anything else to `null`, so a `running` row would render as "has not run yet" — the worst of the available lies. Admit `running`.

## 4. Tests

- [x] 4.1 Rewrite the seeding cases in `tests/test_scheduler.py` around the clock rather than `first_tick`: a slot just past fires; a slot hours past seeds when `catch_up` is false and fires once when it is true.
- [x] 4.2 Add the suspend case: two ticks in one process with the clock jumping across the slot, `catch_up` false, asserting the slot is seeded and nothing fires. This is the case the old rule got wrong.
- [x] 4.3 Add the overrun case: a run that returns after the next configured time has passed, asserting that slot is seeded rather than fired when `catch_up` is false.
- [x] 4.4 Add the reconciliation cases: a row left `running` becomes `failed` at startup, keeping its start instant and gaining an error line; `ok` and `failed` rows are untouched.

## 5. Verification

- [x] 5.1 `uv run pytest -q` green and `uv run ruff check src` clean.
- [x] 5.2 `docker compose build && docker compose up -d`, then drive a real chain through `fire()` in the container and confirm `schedule_state` reads `running` mid-run and `ok` after — the image is baked, so an un-rebuilt container verifies nothing (see `.claude/skills/docker-verify/SKILL.md`).
- [x] 5.3 Check the settings page against a real in-progress run, in both locales, and against a row left `running` by killing the container mid-run.

## 6. Documentation

- [x] 6.1 Update the scheduler section of `docs/` and its `docs/zh/` mirror in the same change: catch-up now covers every missed run, and the panel reports a run in progress. Both languages or it is not done.
- [x] 6.2 Widen the `last_status` column comment in `scripts/bootstrap_db.py` — it enumerates the value domain as `'ok' | 'failed' | NULL`, which is the same two-valued reading that made the dashboard discard a running row. No DDL change, comment only.

## 7. Review follow-ups

- [x] 7.1 Correct the lateness window in the `core-schedule` delta. It said a slot is on time "within the current poll interval" while D1 and the code both use two, which is the one sentence a future reader would take the rule from.
- [x] 7.2 State the other half of the overrun rule in the same delta: with `catch_up` true an overrun slot is caught up like any other missed one, so times spaced closer together than a run takes will start a new run as soon as the previous returns. The change only alters the `catch_up: false` side, and a reader given one half would assume the other.
- [x] 7.3 Reconcile before reading the schedule file, not after. `load_schedule()` raises on a malformed file and the container restarts into the same raise, so a row left `running` would have stayed that way — reported as a run still in flight — for as long as the file stayed broken.
- [x] 7.4 Route the analysis runner's per-item warnings through the same structlog logger as the timing lines. The stdlib handler's `%(message)s` format drops every `extra=` field, so `tier2_failed` and its siblings were saying an item failed without saying which or why — the same blindness this change was opened to fix.
- [x] 7.5 Update `dashboard/README.md` and its `zh-CN` mirror: the schedule group reports four states now, not "how the last run ended", and catch-up no longer covers only a stopped scheduler. `docs/operations.md` and its mirror also still said the chain fires "once a day" two paragraphs above the sentence explaining that every listed time fires.

## 8. Second review pass

- [x] 8.1 Claim the slot and record the run's start in one statement (`claim_slot`), leaving `write_slot` for seeding. Two writes on two connections admit a slot advanced with no run on record — the one interrupted-run state reconciliation cannot see and the panel cannot show, so the day's run is skipped in silence.
- [x] 8.2 Reject a non-boolean `enabled` / `catch_up` instead of coercing it. `bool("false")` is `True`, the file is hand-editable by design, and this is the only path that spends model tokens unattended. Absent stays false; the dashboard's reader stays forgiving, for the reason it always was.
- [x] 8.3 Remove the timezone control. It recorded a zone the scheduler never read, and its only observable effect was the amber warning saying so. State `INFO_RADAR_TIMEZONE` read-only instead; wiring it up would have split the schedule's zone from the day-grouping zone the same value fixes.
- [x] 8.4 Cover all three in tests: the slot/start pairing against real Postgres, the strict booleans across both flags and every wrong type, and the dashboard typecheck for the dropped `tz` field.
- [x] 8.5 Verify in Docker — rebuild, confirm both containers run the new image, check the settings page renders the zone as static text with no `select`, and confirm the scheduler starts clean against the real on-disk file (which still carries a legacy `tz` key, correctly ignored).
