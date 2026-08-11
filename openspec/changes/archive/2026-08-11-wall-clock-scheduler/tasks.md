## 1. Prerequisite

- [x] 1.1 Archive `rename-paca-to-next-signal` before starting. Its delta and this one both MODIFY `knowledge-reindex` → "Workflow runs on demand" and `dashboard-shell` → "A nav settings panel owns the content-language preference". This change's MODIFIED blocks are written against the **post-rename** text, so archiving in the other order will leave them not matching the live spec. This change then RENAMES that requirement to "The settings page owns the content-language preference", because the panel becomes a page here — so every change archived after it modifies the new name.

## 2. Core plumbing

- [x] 2.1 Add `src/next_signal/core/clock.py` with `radar_timezone()` (reads `INFO_RADAR_TIMEZONE` at call time, default `America/Los_Angeles`) and `now_local()`.
- [x] 2.2 Point `workflows/info_radar_recap/store.py` and `workflows/knowledge_review/store.py` at `core.clock`, deleting their local copies. Their existing tests must still pass unchanged.
- [x] 2.3 Add `src/next_signal/core/schedule.py`: a frozen `Schedule` dataclass (`enabled`, `at`, `catch_up`) plus `load_schedule()` reading `<state-root>/schedule.json`. Absent file → disabled; malformed JSON or an `at` that is not a valid in-range `HH:MM` → `RuntimeError` naming the value.
- [x] 2.4 Add `prev_slot(at, now)` returning the most recent occurrence of `at` at or before `now`, timezone-aware.
- [x] 2.5 Add the `schedule_state` DDL to `scripts/bootstrap_db.py` and register the table in `core/db.py`'s `BUSINESS_TABLE_COLUMNS`.
- [x] 2.6 Lift `_run_workflow_now` out of `interfaces/cli.py` into `src/next_signal/orchestrator/run_now.py` as `run_workflow_now`; the CLI imports it. No behavior change.

## 3. Scheduler

- [x] 3.1 Add `src/next_signal/orchestrator/schedule.py` with the `schedule_state` reads/writes: read all rows, upsert `last_slot_at`, write run outcome (`last_run_at` / `last_status` / `last_error`). Bare short-lived `psycopg.connect(database_url())`.
- [x] 3.2 Implement `_fire()`: run `info_radar_pull` then `info_radar_analysis` through `run_workflow_now`, stopping at the first failure, recording the outcome, never propagating out of the loop. Log structured events, including each leg's
  duration and the workflow's own run summary — an unattended run is recorded
  nowhere else, and the 2026-08-10 80-minute run could not be explained without
  it. Each summary must therefore hold only counters and names: `info_radar_pull`
  reports which sources failed, not their error text, because that text is the
  source CLI's own stderr and `run_all` has already logged it in full at the
  point it happened. The blanket "no result dicts" this task originally carried
  is narrower than it read: it guards against dumping provider payloads, not against a
  counters summary.
- [x] 3.3 Implement `run()`: 30s poll loop that re-reads the schedule file each tick, applies both seeding rules (effective-schedule change or missing row; process start when `catch_up` is false), advances `last_slot_at` before firing, and skips all work while disabled.
- [x] 3.4 Log on start: resolved timezone plus whether a schedule is configured.

## 4. Entry points

- [x] 4.1 Add the `next-signal schedule` command to `interfaces/cli.py` (no flags) calling `orchestrator.schedule.run()`.
- [x] 4.2 Correct the `run-workflow` docstring, which currently claims there is no background scheduler.
- [x] 4.3 Add the `scheduler` service to `docker-compose.yml`: `<<: *app`, `command: ["next-signal", "schedule"]`, gated on `postgres` healthy and `bootstrap` completed. No Compose profile.

## 5. Dashboard

- [x] 5.1 Add `scheduleStateFile()` to `dashboard/lib/paths.ts`.
- [x] 5.2 Add `dashboard/lib/actions/schedule.ts`: `getSchedule()` (forgiving — bad file reads as disabled and logs), `setSchedule()` (atomic temp-file + rename, `updated_at` / `updated_by` like `language.ts`), `getScheduleStatus()` (reads the `schedule_state` row through the existing `pg` pool).
- [x] 5.3 Move settings out of the nav popover onto a `/settings` page — four sections do not fit an anchored panel — and add the schedule section there, separated from the content-language one: `Segmented` for enabled and for catch-up, `Input type="time"` per time row, a timezone select, all hidden while disabled. The nav gear becomes a link; `components/settings-panel.tsx`, `components/ui/popover.tsx`, its Radix dependency, and its `/design` entry are retired. No new UI primitive.
- [x] 5.4 Render the last-run read-back (never / succeeded / failed + relative time via the existing helper), with the recorded error reachable when the last run failed.
- [x] 5.5 Wire the panel's initial state from the server so it paints with no loading state, matching how `contentLanguage` is passed in today.
- [x] 5.6 Add `en` and `zh` dictionary entries, including the hint stating that catch-up covers only runs missed while the scheduler was down and that changing the schedule never fires a slot that just passed.

## 6. Tests

- [x] 6.1 `prev_slot`: before/after the time on the same day, and across a DST boundary (assert the behavior is defined, not that it is minute-perfect).
- [x] 6.2 `load_schedule`: absent file → disabled; malformed JSON → `RuntimeError`; `"25:00"` and `"8am"` → `RuntimeError`.
- [x] 6.3 Seeding rules, against a real Postgres: first sight always seeds; `(enabled, at)` change re-seeds without firing; process start with `catch_up` false seeds; with `catch_up` true does not.
- [x] 6.4 Due-ness: several elapsed slots collapse to one run; a completed slot does not re-fire on restart.
- [x] 6.5 `_fire`: a failing first stage skips the second, records `last_status='failed'` with the stage named, and does not propagate.

## 7. Container verification

Per `.claude/skills/docker-verify/SKILL.md`; `docker compose build` first, since `/app` is image-baked. Use a chain reduced to `info_radar_pull` where possible so verification spends no model tokens.

- [x] 7.1 `docker compose up -d` with no `schedule.json`: the `scheduler` service starts, logs itself idle, and does not restart-loop.
- [x] 7.2 Set a time ~2 minutes out from the dashboard panel; confirm the running scheduler picks it up within one poll with no restart, and fires at the slot.
- [x] 7.3 Catch-up off (default): stop the service, let a slot elapse, start it — no run.
- [x] 7.4 Catch-up on: same sequence — exactly one run, and the next polls find nothing due.
      Verified organically rather than by a forced run: the scheduler fired its own 13:55 slot at
      2026-08-09 21:14 UTC, ran pull then analyze over 35 items, and recorded `last_status='ok'`
      on the `radar` row — a column only `fire()` writes, so a manual `run-workflow` cannot
      account for it. The seeding/collapse decisions are additionally covered against real
      Postgres by `test_process_start_with_catch_up_runs_the_missed_slot` and
      `test_many_missed_times_still_collapse_to_one_run`.
- [x] 7.5 Change the time to a moment that has just passed — no run fires.
- [x] 7.6 Disable then re-enable the schedule — no run fires.
- [x] 7.7 Restart the container after a completed run — the same slot does not replay.
- [x] 7.8 Confirm the panel's read-back is correct after one successful and one failed run.

## 8. Docs and spec sync

- [x] 8.1 `docs/operations.md` — add `next-signal schedule`; drop the "manual trigger only / no background scheduler" annotation on `info-radar analyze`.
- [x] 8.2 `docs/modules/info_filter.md` — replace the manually-triggered-only statement with the schedule, keeping the point that `seen_at` is what makes any cadence safe.
- [x] 8.3 `docs/containerized-deployment.md` — document the `scheduler` service and the "nothing fires while Docker is not running" limit.
- [x] 8.4 `dashboard/README.md` — the new settings section.
- [x] 8.5 Mirror 8.1–8.4 into `docs/zh/` and `dashboard/README.zh-CN.md` in this same change — a one-language doc change is an unfinished doc change.
- [x] 8.6 `openspec validate wall-clock-scheduler --strict` passes, and `openspec status --json` shows no unmatched delta before archiving.

## 9. Review follow-ups

Found reviewing the branch as a whole, before archiving.

- [x] 9.1 Rewrite the `dashboard-shell` delta against what shipped. The requirement was still specifying the `Popover` primitive, the anchored nav panel, "timezone as literal text", and "SHALL NOT display a next-run" — all four contradicted by the page that landed. Adds the `RENAMED` op, the `Global app shell` modification the removed host chip needs, and the concurrent-write clause.
- [x] 9.2 Bound the free-hour search in the schedule section's add-time control. It was a `while` over a mod-24 counter, so a schedule holding all twenty-four hours hung the tab with no error.
- [x] 9.3 Compute the section's next-run line in the zone the scheduler resolves rather than the recorded one. The original requirement banned a next-run precisely because a wrongly-zoned one is confidently wrong; computing it in the zone in force answers the question instead of forbidding it.
- [x] 9.4 Collapse the four hand-rolled state-file writers onto one `lib/state-file.ts` with a per-write temp path, covered by `lib/state-file.test.ts`. Two of them shared a fixed `.tmp`, which measured as a deterministic failure rather than a rare one: with two saves in flight the first rename consumes the temp file and the second fails every time, so the settings page reports a save that failed and rolls the control back — while a perfectly valid file sits on disk. The test fails against the shared path and passes against the unique one.
- [x] 9.5 Correct `dashboard/lib/paths.ts`'s `engineStateFile` comment, which still said the file did not steer a run, and delete the orphaned `.brand .env` rule this change's nav edit left behind.
- [x] 9.6 `CLAUDE.md`: add `next-signal schedule` to the CLI list, noting it is the one path that spends tokens unattended, and `schedule_state` to the business-table list. `.claude/skills/docker-verify/SKILL.md`: add `/settings` to both page lists, correct the "three read-only GET routes" claim now that the coding-agent auth route accepts POST/PUT/DELETE, and give the `scheduler` service its own entry in the token-spend section.
- [x] 9.7 `docs/architecture.md` + `docs/zh/` — add the `coding_agents/` domain to the integrations layer.
