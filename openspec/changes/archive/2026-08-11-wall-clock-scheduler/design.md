## Context

The radar pipeline is two CLI-invocable workflow shells — `info_radar_pull`
(no LLM, hits source CLIs, writes `radar_items`) and `info_radar_analysis` (the
two-tier LLM pipeline, writes `radar_analyses`). Both already declare
`extra.run_now` in their YAML, and `run_workflow_now()` already resolves and
calls it. So a scheduler needs to know nothing about the radar: it needs to know
*when*, and to call two workflow names in order. That resolver lives in
`orchestrator/run_now.py` rather than the CLI, because the CLI's `run-workflow`
and the scheduler's chain are both callers of it.

Two facts shape the whole design:

1. **The stack ships as Docker Compose.** `postgres` (long-running),
   `bootstrap` (one-shot), `dashboard` (long-running). The host OS never runs
   project code directly, so the cron/launchd/Task-Scheduler split never has to
   be confronted — a fourth service is the whole cross-platform story.
2. **The target machine is a laptop.** It sleeps, it gets closed at 3am, Docker
   Desktop gets quit. A scheduler that models time as "a timer I set when I
   started" is wrong here; it has to re-derive what it owes from wall clock and
   durable state on every check.

The dashboard already has the exact precedent for an operator-editable runtime
setting: `~/.next-signal/language.json`, written atomically by a server action
from the settings page, read by the Python pipeline, with a forgiving
reader on the dashboard side and a loud one on the pipeline side.

## Goals / Non-Goals

**Goals:**

- A set of wall-clock daily times triggers `info_radar_pull` →
  `info_radar_analysis` unattended, identically on macOS, Windows, and Linux.
  Every listed time fires every day.
- A run missed because the machine was asleep or Docker was quit is either
  skipped (default) or run once on next start — the operator's choice.
- The schedule is configured from the dashboard, next to the existing
  content-language setting, and is hand-editable as a file.
- The operator can tell from the UI whether the last run succeeded.
- Config changes take effect without restarting the container.

**Non-Goals:**

- Cron expressions, intervals, weekday filters. The requirement is a set of
  wall-clock times of day; anything more is unrepresentable in the UI being
  built and would create states the panel cannot render.
- More than one job. The chain is fixed in code.
- Retries, backoff, run history, per-job timezones, sub-minute precision, a
  "run now" button (each pipeline already has its own manual trigger).
- Firing while the container host is not running Docker. Impossible from inside
  a container; `catch_up` is the mitigation, not a fix.

## Decisions

### D1. Store the last handled *slot*, not the last run time

`schedule_state.last_slot_at` holds the most recent scheduled calendar instant
already dealt with — not when execution happened. A run is due exactly when:

```
prev_slot(at, now) > last_slot_at
```

where `prev_slot` is the most recent occurrence of `at` at or before `now`.

This single comparison is what makes every hard case fall out for free:

- **Restart mid-day** — `prev_slot` is unchanged, nothing fires twice.
- **Down for two days** — `prev_slot` is far ahead of `last_slot_at`, so the
  gap is *detected* rather than silently lost.
- **Host suspend** — every tick re-reads the wall clock and compares against
  Postgres, so a suspended VM is just one unusually long tick. No wake-up
  hooks, no monotonic-vs-wall-clock hazard.
- **Multiple missed slots** — jumping straight to `prev_slot` collapses them
  into one run. Firing four times to "catch up" is never what anyone wants.

*Alternative considered:* store `last_run_at` and compare against a computed
next-fire time. That conflates "when the schedule wanted to run" with "when it
actually did", and every one of the cases above then needs its own special case.

### D2. Poll every 30s; do not sleep until the next fire time

Sleeping until the next computed fire is more elegant and wrong here.
`time.sleep` on Linux is not guaranteed to account for host suspend, and inside
a Docker Desktop VM the whole guest can be paused. Dumb polling re-derives
everything from wall clock + DB each tick, so it is correct under suspend by
construction, and it is what lets the config be re-read live (D4).

### D3. `HH:MM` times in the config, not a cron expression

An earlier draft used cron expressions with `croniter`. Once the dashboard
requirement landed, that became wrong: the panel can only express "every day at
these times", so a cron string admits values the UI cannot render, forcing a
read-only "custom expression" state that exists purely to apologise for the
format. Storing `at: ["HH:MM", ...]` makes file and UI exactly as expressive as
each other, and drops the dependency — `prev_slot` is the latest of the
per-time candidates:

```python
def _slot_for(at, now):
    hour, minute = parse_at(at)
    slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return slot if slot <= now else slot - timedelta(days=1)

return max(_slot_for(t, now) for t in times)
```

Several daily times cost one `max`, and nothing downstream changes: due-ness
stays "is the current slot newer than the one already handled?". A bare string
is still accepted on read, because files written before multiple times existed
are still on disk; that is a migration, not a fallback, and the next dashboard
write stores a list.

`now` is timezone-aware (`ZoneInfo`), and `timedelta` arithmetic on an aware
datetime is wall-clock arithmetic, so "yesterday at 08:00" stays 08:00 across a
DST boundary. On the one spring-forward day where the configured wall time does
not exist, `fold` resolution yields a defined instant up to an hour off, and the
next day self-corrects. Handling that properly is not worth code.

*Trade-off accepted:* "weekdays only" is still impossible, and "every 6 hours"
is expressible only by listing the four times.
Re-introducing `croniter` is the move if either is ever needed, and it is
additive to this design — `prev_slot` is the only function that changes.

### D4. Config is a state file, re-read every tick

`~/.next-signal/schedule.json`, mirroring `language.json` field-for-field
(`updated_at` / `updated_by`), written atomically (temp file + rename) by a
dashboard server action.

`configs/schedules.yaml` in the repo was the earlier draft and is wrong for a
dashboard-writable setting: CLAUDE.md puts operator-editable runtime state in
`~/.next-signal/`, the state directory is already a Docker volume, and the repo
tree inside the container is image-baked and therefore not writable in any way
that survives.

Re-reading the small file on every 30s tick means a change made in the dashboard
takes effect within half a minute, with no restart, no signal handling, and no
file-watch machinery.

**An absent file means disabled.** This is not a silent default papering over a
missing config — absence genuinely means "never configured", and off is the only
safe reading of that. It is the same call `getContentLanguage()` already makes
for a missing `language.json`. The consequence is that the `scheduler` service
can be unconditional in `docker-compose.yml`: a user who never opens the panel
gets an idle container, not a crash loop, so no Compose profile is needed.

### D5. Two seeding rules, and `catch_up` only governs one of them

"Seeding" means writing `last_slot_at = prev_slot(now)` *without* running —
declaring past slots handled.

- **Rule A — the effective schedule changed.** When `(enabled, at)` differs from
  the previous tick's value, or no row exists yet, re-seed. Setting the time to
  08:00 at noon must not immediately fire this morning's 08:00, and switching the
  schedule on must not fire a backlog.
- **Rule B — process start.** On startup, seed once if `catch_up` is false. If
  it is true, skip seeding and let the ordinary due-check notice the gap and fire
  once.

> **Rule B is superseded** by the `scheduler-run-state` change, which replaces
> "did the process just start?" with "did this slot come due within twice the
> poll interval?". Anchoring to process start makes `catch_up` inert for the most
> common miss on a laptop, where the process survives the suspend that caused it.
> Rule A is unchanged, and so is the sentence below it, which is the part that
> was load-bearing.

So **`catch_up` means "run a slot missed while I was down"; it never means "run
because the configuration just changed"**, and it never means "run once because
there is no history". A job seen for the first time is always seeded. This
distinction is load-bearing enough that the settings page states it in its hint
text rather than leaving the operator to discover it.

### D6. Advance the slot before running; advance it even on failure

`last_slot_at` is written before `fire()` is called. If the container is killed
mid-run, the slot is consumed and will not replay — a partially-completed radar
run re-running on restart is worse than a skipped one, since `analyze` costs
model tokens.

That write is a single statement that also records the run as started
(`claim_slot`), rather than two writes on two connections. Consuming a slot and
beginning a run are one decision, and split in two they admit a state in which
the slot is spent with no run on record — which nothing downstream can detect:
startup reconciliation looks for an in-progress row and finds none, and the panel
keeps displaying the previous run. Seeding keeps its own write (`write_slot`),
because no run begins there.

A failed run also advances the slot: the next attempt is tomorrow's slot, not 30
seconds from now. A broken job that hammers the pipeline every tick would burn
tokens and bury the logs. The failure is recorded in `last_status` / `last_error`
for the UI and logged at error level, so it is loud without being repetitive.

### D7. The chain is in code; a failing step stops the rest

`fire()` runs `info_radar_pull` then `info_radar_analysis`, stopping at the
first failure — analysing a batch that failed to pull is pointless. Exceptions
are caught at the chain level so one bad run never kills the loop, which matches
the established "one bad YAML must not take down the loader" posture. This is not
silent-defaulting: the error is logged and persisted.

### D8. `radar_timezone()` moves to `next_signal.core.clock`

It is currently defined twice — in `workflows/info_radar_recap/store.py` and
`workflows/knowledge_review/store.py` — and the scheduler is the third consumer.
`orchestrator` importing a specific workflow's `store` would also invert the
layering, since both sit on the same tier. Two copies were tolerable; three is
the point where it converges. Reusing the existing `INFO_RADAR_TIMEZONE` env var
(rather than adding a scheduler-specific one) also means the schedule fires on
the same local day boundary the dashboard already displays.

### D9. The panel states the timezone; any next-fire time is computed in it

The browser's timezone and `INFO_RADAR_TIMEZONE` need not agree, so a
client-computed "next run at ..." can be confidently wrong. The panel therefore
names the zone in force and resolves its next-run line in *that* zone rather than
the browser's — `Next run tomorrow at 08:00 · Asia/Shanghai`.

The zone is stated, never chosen. An earlier build offered a zone picker whose
value the scheduler did not read, alongside a warning that it did not; a control
whose only observable effect is a warning that it has no effect should not exist.
Wiring it up instead was the wrong fix: `INFO_RADAR_TIMEZONE` is one
environment-wide decision shared with radar day grouping and review due dates
(D8), so a schedule with a zone of its own would fire at 08:00 in one zone while
its results were filed under a day boundary drawn in another — the exact bug D8
consolidated the helper to prevent.

The last-run read-back comes from `schedule_state` through the existing `pg` pool
and the existing `relative-time` helper.

### D10. No new UI primitive

Both binary controls (on/off, skip/catch-up) reuse the existing `Segmented`
component the content-language setting already uses; the time uses `Input` with
`type="time"`, which the component already passes through to the underlying
`<input>` with `.input` styling intact. This keeps the panel visually of a piece
with the section above it and avoids the `/design` catalogue obligation that a
new primitive would carry.

## Risks / Trade-offs

- **Docker not running → nothing fires.** → Unfixable from inside a container;
  `catch_up: true` converts a missed window into one run at next start. Stated
  plainly in the docs rather than worked around.
- **`analyze` runs longer than the tick interval.** → The loop is single-threaded
  and runs jobs inline, so overlap is structurally impossible; ticks simply do
  not happen while a run is in flight.
- **Scheduled `analyze` silently burning model tokens.** → The chain is fixed and
  visible, the schedule defaults to off, and the settings page reports the last
  run so an unnoticed nightly run is not possible for long.
- **DST spring-forward on the configured time.** → Up to one hour of drift, once
  a year, self-correcting the next day. Accepted; worth a unit test asserting the
  behavior is defined rather than crashing.
- **Config file hand-edited to something invalid.** → The pipeline-side reader
  raises loudly (matching `core.language`), and the dashboard-side reader falls
  back to disabled and logs, so a bad file can still be fixed from the panel that
  displays it.
- **Clock skew between the scheduler container and Postgres.** → All comparisons
  are made in the scheduler process against values it wrote itself; Postgres is
  storage, never the clock source.
