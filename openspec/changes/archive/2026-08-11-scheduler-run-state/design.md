## Context

The wall-clock scheduler collapses every awkward case — host sleep, container restart, Docker quit for a weekend — into one comparison: is the most recent scheduled slot newer than the last slot handled? That reduction is sound, and this change keeps it. What it got wrong is the *second* question, asked only when the answer is yes: was this slot missed, or is it merely due? Today that is answered with `first_tick`, a property of the process rather than of the clock, and a suspended laptop is precisely the case where the process outlives the miss.

The second half of the change is about what the operator can see. `schedule_state` records only terminal outcomes, so a run is invisible for its whole duration. On 2026-08-10 a chain that started on time at 08:00:22 finished at 09:21:02; for those eighty minutes the settings page showed the previous run, then flipped to "just now". Establishing that the run had not been a late catch-up took a cross-referenced reading of the container log and OMLX's own server log.

Both halves are small, and both are about the scheduler describing itself accurately, so they ship together.

## Goals / Non-Goals

**Goals:**

- `catch_up` decides every missed run, whatever caused the miss.
- One rule covers process restart, container restart, host suspend, and a poll delayed by an overrunning run.
- A run in progress is readable from `schedule_state`, and a run the process never finished does not stay readable as in progress.
- The settings page distinguishes never-run, in progress, succeeded, and failed.

**Non-Goals:**

- No DDL, and no new status value beyond `running`. `last_status` is unconstrained text; `last_run_at` carries the start instant until the terminal write replaces it.
- No progress detail — no stage, no item counts, no percentage. The counters now logged by `schedule_run_done` (commit `e68d547`) cover diagnosis; the panel only answers "is it running, and for how long".
- No live-updating panel. The state is read when the page renders.
- Nothing about why the 2026-08-10 run took eighty minutes. That is a separate, still-open investigation.

## Decisions

### D1. Lateness is measured against the poll interval, not against process start

A due slot is **on time** when `now - prev_slot <= 2 * tick_seconds`, and **late** otherwise. `tick()` takes `tick_seconds` in place of `first_tick`.

The doubled interval is grace, not precision: the loop sleeps exactly `tick_seconds`, so a slot is normally noticed within one interval, and the second interval absorbs a poll made slow by its own database reads. Every real miss this rule has to catch is minutes to days late, so the boundary has no near neighbours — sizing it exactly would be false precision.

*Alternative considered — remember the previous tick's wall clock and call a slot on time when it came due after it.* Rejected: it is more faithful for suspend (the previous tick was before the suspend, so the slot is correctly late) but wrong for the overrun case, where the previous tick is 80 minutes old and every slot since would read as on time. The interval comparison gets both right with less state.

*Consequence, accepted:* a container that restarts within 2 × 30s of a slot now fires it, where the old rule always seeded at process start. This is the right reading — the slot came due seconds ago and nothing was missed — and it cannot loop, because `last_slot_at` advances before the chain runs.

### D2. The lateness rule lives in the orchestrator, not in `core.schedule`

`prev_slot` stays a pure function of the configured times and the clock. Lateness depends on the poll interval, which is a property of the loop, so it belongs beside the loop. `core.schedule` continues to answer "which slot is current"; `orchestrator.schedule` continues to answer "what do we do about it".

### D3. One writer for all three run states

`write_outcome` becomes `write_run_state(job, *, status, error)`, called with `running` before the chain, then `ok` or `failed` after it. The SQL is identical for all three, and a second near-duplicate function would drift.

The in-progress record is written once per *chain*, not once per workflow leg. The operator's question is whether the radar is running, not which of the two workflows it is inside; the leg is already in the logs.

### D4. An interrupted run is reconciled at startup, not detected by age

`run()` rewrites a row still marked `running` before entering the loop, keeping `last_run_at` (the start instant) and recording an error line saying the process exited mid-run.

Startup is sufficient because it is the only way the record goes stale: the poll loop executes jobs inline on a single thread, so a `running` row observed by the process that wrote it is genuinely running. Two schedulers against one database would each reconcile the other, but compose runs one and `core-schedule` already specifies that overlapping runs are impossible.

*Alternative considered — a heartbeat column with a staleness threshold.* Rejected: it needs DDL, a timer writing during the run, and a threshold to tune, to cover a case startup reconciliation already covers exactly.

### D5. Reconciliation writes `failed`, not a status of its own

An earlier draft gave the interrupted case its own `last_status` value. It does not earn one. `schedule_state` holds **one row per job, overwritten by the next run** — there is no run history — so a distinct value can never be counted or grouped over time; its only effect is how the current row renders, and it renders exactly as a failure. What actually distinguishes "the process died" from "a workflow raised" is `last_error`, which the reconciliation writes either way.

So the panel branches on `running` and otherwise keeps its existing three-way read-back, with any other status falling into the failure branch. That costs one new dictionary entry — for the in-progress line — and nothing else.

Elapsed time reuses the existing `timeAgo` helper against `lastRunAt`, which during a run holds the start instant.

## Risks / Trade-offs

- **The panel's elapsed time is frozen at page load** → The section already samples `now` once on mount to avoid a hydration mismatch, and the status itself comes from a server render, so a ticking clock would keep counting past a run that had already finished. A refresh is the honest way to get a current answer; no timer is added.
- **A restart within one poll interval of a slot now fires it** → Bounded by D1's window and made idempotent by advancing `last_slot_at` first. The alternative — keeping the process-start special case as well — would reintroduce exactly the ambiguity this change removes.
- **The lateness comparison inherits `prev_slot`'s DST slop** → `_slot_for` builds the slot with `now.replace(...)`, which its own docstring admits can land up to an hour off on a transition day. A time configured *inside* the transition hour can therefore read as an hour late on that one day and be skipped with catch-up off. One slot, once a year, failing toward "skip" — which is what the setting asks for anyway — so it is recorded rather than coded around.
- **`tests/test_scheduler.py` is written around `first_tick`** → Its clock is already substituted, so each case becomes a choice of how far past the slot the clock sits. The rewrite is mechanical, but it is a rewrite, not an edit, and the suspend and overrun cases are new.
- **This change's `dashboard-shell` delta overwrites whatever wording `wall-clock-scheduler` lands** → That change now renames the requirement to "The settings page owns the unattended run schedule" and states the page's read-only timezone line and its next-run line; the copy here matches it clause for clause and adds only the in-progress read-back. Both were updated together when the timezone picker was removed. Re-check the pair at archive time rather than trusting this note.

## Migration Plan

Nothing to migrate: no schema change, and no state file format change. A running scheduler picks the new behaviour up on rebuild and restart.

Archive ordering is the one constraint. Both modified requirements live in `wall-clock-scheduler`'s deltas rather than in `openspec/specs/`, so that change — together with `add-coding-agent-cli-bridge`, which must be archived alongside it — has to be archived before this one, or the `MODIFIED` headers here will have nothing to modify.

## Open Questions

- If the container turns out to be killed mid-run often, what would answer "how often"? Not a status value (D5) — `schedule_state` keeps no history. It would take a run-history table, which nothing has asked for yet; until then the container log is the record.
