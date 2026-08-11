# core-schedule Specification

## Purpose
TBD - created by archiving change wall-clock-scheduler. Update Purpose after archive.
## Requirements
### Requirement: Schedule configuration is an operator-editable state file

The schedule SHALL be stored at `<state-root>/schedule.json` (`~/.next-signal/schedule.json` by default, honouring `NEXT_SIGNAL_STATE_DIR`), holding `enabled` (boolean), `at` (a list of `HH:MM` 24-hour local times), and `catch_up` (boolean), alongside the `updated_at` / `updated_by` provenance fields `language.json` already carries. Writers SHALL write atomically — temp file plus rename — so a concurrent reader never observes a torn file.

`at` SHALL be a set of daily times: **every listed time fires every day**. Readers SHALL deduplicate and sort it, and SHALL drop blank entries, so the stored form is canonical. Readers SHALL also accept a bare string in place of a list and read it as a single time — the field held one time before multiple daily runs existed, and files written by that version remain on disk. This is a migration, not a fallback: the next write stores a list.

An absent file SHALL be read as `enabled: false`. Absence means the operator has never configured a schedule, and disabled is the only safe reading of that; this is not a fallback masking a misconfiguration. A file that exists but is malformed, holds an `at` that is neither a string nor a list, or holds any time that is not `HH:MM` with an in-range hour and minute, SHALL raise `RuntimeError` on the pipeline side rather than degrade to a default. An `enabled` schedule with no times SHALL raise, since it has nothing to fire.

The time SHALL be interpreted in the timezone returned by `next_signal.core.clock.radar_timezone()` — the same `INFO_RADAR_TIMEZONE` value (default `America/Los_Angeles`) that decides the radar's local day — so a scheduled run and the day it lands on agree.

#### Scenario: no schedule has ever been configured

- **WHEN** the scheduler starts and `~/.next-signal/schedule.json` does not exist
- **THEN** it reads the schedule as disabled, runs no workflow, and does not create the file

#### Scenario: malformed time fails loudly

- **WHEN** the file holds `"at": "25:00"` or `"at": "8am"`
- **THEN** the pipeline-side reader raises `RuntimeError` naming the offending value

#### Scenario: a torn read is not possible

- **WHEN** the dashboard writes a new schedule while the scheduler is reading the file
- **THEN** the reader observes either the complete previous content or the complete new content, never a partial write

### Requirement: Due-ness is decided by the last handled slot

The `schedule_state` row for a job SHALL hold `last_slot_at`, the most recent scheduled instant already dealt with — not the time execution occurred. The scheduler SHALL compute `prev_slot`, the most recent occurrence of **any** configured time at or before now in the radar timezone, and SHALL consider a run due exactly when `last_slot_at < prev_slot`.

Because due-ness is a single comparison against the latest elapsed slot, the number of configured times is not a special case: one time and several times use the same code path, and each configured time becomes its own run as it comes due.

Multiple slots that elapsed while the scheduler was not running SHALL collapse into a single run: the scheduler advances directly to `prev_slot` rather than replaying each missed occurrence. With several daily times this means one run, not one per missed time.

#### Scenario: restart within the same day does not re-fire

- **WHEN** the 08:00 run has completed and the container is restarted at 14:00 the same day
- **THEN** `prev_slot` is still that day's 08:00, which equals `last_slot_at`, and nothing fires

#### Scenario: each configured time is its own run

- **WHEN** the schedule lists 08:00, 13:00, and 20:00, and the scheduler runs through a full day
- **THEN** the chain runs three times, once as each time comes due

#### Scenario: nothing fires between two configured times

- **WHEN** the 08:00 slot has been handled and the clock reads 12:59 with 13:00 configured
- **THEN** no run occurs, because the latest elapsed slot is still 08:00

#### Scenario: adding a time does not fire one that just passed

- **WHEN** 11:00 is added to the schedule at 12:00, with catch-up enabled
- **THEN** no run occurs and that day's 11:00 is seeded as handled, because a schedule change is not a missed run

#### Scenario: several missed days collapse into one run

- **WHEN** the scheduler has been down for three days with `catch_up` enabled and starts at 10:00
- **THEN** at most one run occurs, for the most recent 08:00 slot, not one per missed day

#### Scenario: host suspend is not a special case

- **WHEN** the host sleeps through the scheduled time and resumes afterwards
- **THEN** the next poll re-reads the wall clock, finds `prev_slot` beyond `last_slot_at`, and the configured catch-up policy decides the outcome — no wake-up notification is required

### Requirement: Seeding declares past slots handled without running them

Seeding SHALL mean writing `last_slot_at = prev_slot` **without** executing the job. The scheduler SHALL seed in exactly two situations:

- when the effective schedule — the pair `(enabled, at)` — differs from the value observed on the previous poll, or no `schedule_state` row exists for the job; and
- when the due slot is late and `catch_up` is false.

A due slot SHALL be **on time** when it came due within twice the poll interval, and **late** otherwise. The doubled window is grace rather than precision — one interval is when a slot is normally noticed and the second absorbs a poll made slow by its own database reads, while every real miss is minutes to days late, so the boundary has no near neighbours. Lateness SHALL be derived from the wall clock alone, never from whether the process has just started. A container that has been down for a day, a host that suspended through the slot, and a poll delayed by a run that overran are the same event — a slot came due while nobody was watching — and SHALL be treated identically. Anchoring the decision to process start instead makes `catch_up` inert for the most common miss on a laptop, where the process survives the suspend.

Consequently `catch_up` SHALL govern every missed run, however the miss occurred. It SHALL NOT cause a run because the configuration was just changed, because the schedule was just enabled, or because the job has no history. A job seen for the first time SHALL always be seeded.

A slot that comes due while the previous run is still executing SHALL be late by this rule, and therefore skipped when `catch_up` is false, rather than firing the moment the previous run returns. A single radar run can take longer than the gap between two configured times, and stacking a second run onto the end of an overrunning one is worse than skipping it.

With `catch_up` true that same slot SHALL be caught up like any other missed one, which for times spaced closer together than a run takes means a new run beginning as soon as the previous one returns. This is the cost of asking for missed runs to be honoured, and is the reason the two settings are not interchangeable at close intervals.

#### Scenario: a slot that comes due while the scheduler is watching fires

- **WHEN** the scheduler is polling normally and the clock passes a configured 08:00
- **THEN** the chain fires on the next poll, regardless of the `catch_up` setting, because the slot is on time rather than missed

#### Scenario: setting the time does not fire the slot that just passed

- **WHEN** the operator sets the time to 08:00 at 12:00 on the same day
- **THEN** that day's 08:00 slot is seeded as handled and no run occurs, regardless of the `catch_up` setting

#### Scenario: enabling the schedule does not fire a backlog

- **WHEN** the operator switches the schedule from disabled to enabled at 12:00, with `catch_up` enabled
- **THEN** no run occurs, because enabling is a schedule change rather than a missed run

#### Scenario: catch-up disabled skips a missed slot

- **WHEN** the scheduler starts at 10:00 with `catch_up` false, and the 08:00 slot elapsed while it was down
- **THEN** the 08:00 slot is seeded as handled and no run occurs

#### Scenario: catch-up enabled runs a missed slot once

- **WHEN** the scheduler starts at 10:00 with `catch_up` true, and the 08:00 slot elapsed while it was down
- **THEN** exactly one run occurs, and the subsequent polls find nothing due

#### Scenario: a host that suspends through the slot honours the catch-up setting

- **WHEN** the host sleeps through the configured 08:00 and resumes at 09:30, with the scheduler process still alive across the suspend and `catch_up` false
- **THEN** the 08:00 slot is seeded as handled and no run occurs, exactly as if the process had been restarted

#### Scenario: a run that overruns the next configured time does not stack

- **WHEN** 08:00 and 09:00 are both configured with `catch_up` false, and the 08:00 run is still executing at 09:20
- **THEN** the 09:00 slot is seeded as handled when the loop resumes, and no second run starts

### Requirement: The scheduler polls rather than sleeping until the next fire

The scheduler SHALL re-read the schedule file, the wall clock, and `schedule_state` on a fixed poll interval of 30 seconds, deriving due-ness afresh each time. It SHALL NOT compute a duration and sleep until the next fire time, because a suspended host or VM makes an elapsed-time sleep an unreliable measure of wall-clock progress.

Because the file is re-read every poll, a schedule edited from the dashboard SHALL take effect without restarting the scheduler process or container.

#### Scenario: dashboard edit takes effect without a restart

- **WHEN** the operator changes the scheduled time in the dashboard
- **THEN** the running scheduler observes the new value on its next poll, within 30 seconds, with no restart

#### Scenario: disabled schedule performs no work

- **WHEN** the schedule is disabled
- **THEN** each poll reads the file, does nothing else, and writes no `schedule_state` row

### Requirement: A due slot runs the radar chain in order

When a run is due, the scheduler SHALL invoke `info_radar_pull` and then `info_radar_analysis`, in that order, through each workflow's declared `extra.run_now` entry point. The chain SHALL stop at the first failing step, since analysing a batch whose pull failed is pointless.

A failure in the chain SHALL be caught at the chain level: it SHALL be logged at error level and persisted, and SHALL NOT terminate the poll loop. The chain composition SHALL live in code rather than in the schedule file — the file configures when, not what.

#### Scenario: successful run executes both stages in order

- **WHEN** a slot comes due and both workflows succeed
- **THEN** `info_radar_pull` runs to completion before `info_radar_analysis` starts, and the run is recorded as successful

#### Scenario: a failed pull stops the chain

- **WHEN** `info_radar_pull` raises
- **THEN** `info_radar_analysis` is not invoked, the error is logged and recorded, and the poll loop continues

#### Scenario: overlapping runs are impossible

- **WHEN** a run takes longer than the poll interval
- **THEN** no second run starts, because the loop executes jobs inline on a single thread

### Requirement: The slot advances before the run and regardless of its outcome

The scheduler SHALL write `last_slot_at = prev_slot` **before** invoking the chain, so that a process killed mid-run does not replay the slot on restart — a partially completed radar run repeating is worse than a skipped one, because `info_radar_analysis` spends model tokens.

The slot SHALL also advance when the chain fails, so the next attempt is the next scheduled slot rather than the next poll. A failing job SHALL NOT retry every 30 seconds.

#### Scenario: a killed run does not replay

- **WHEN** the container is killed while the chain is executing, and restarted afterwards
- **THEN** that slot is already recorded as handled and does not run again

#### Scenario: a failed run waits for the next slot

- **WHEN** the chain fails at 08:00
- **THEN** no further attempt is made until the next day's 08:00 slot

### Requirement: Each run records its outcome for read-back

After each attempt the scheduler SHALL record `last_run_at`, `last_status`, and `last_error` (the failing workflow name and message, or null) on the job's `schedule_state` row, so the dashboard can report whether unattended runs are actually succeeding. For a completed attempt `last_status` SHALL be its terminal outcome — succeeded or failed — and `last_run_at` SHALL be the instant it finished.

`last_status` SHALL NOT be specified as a two-valued field. It also carries the in-progress state required by *A run records that it started, and an interrupted run is reconciled*, and a reader admitting only the terminal pair reports a state it does not recognise as no run at all — which is precisely how a run in progress came to be displayed as a run that never happened.

#### Scenario: a successful run clears the previous error

- **WHEN** a run succeeds after a previous failure
- **THEN** `last_status` becomes `'ok'`, `last_error` becomes null, and `last_run_at` is updated

#### Scenario: a failed run names the failing stage

- **WHEN** `info_radar_analysis` fails
- **THEN** `last_status` is `'failed'` and `last_error` identifies `info_radar_analysis` together with the error message

#### Scenario: a reader admits every state the scheduler writes

- **WHEN** a reader of `schedule_state` encounters a `last_status` outside the terminal pair
- **THEN** it reports that state rather than discarding it as absent

### Requirement: The scheduler runs as an unconditional container service

`docker-compose.yml` SHALL define a long-running `scheduler` service built from the shared app image, running `next-signal schedule`, gated on Postgres health and successful `bootstrap` completion, with the same `restart: unless-stopped` policy the other long-running services use.

The service SHALL NOT be gated behind a Compose profile. Because an absent schedule file reads as disabled, an operator who never configures a schedule gets an idle container rather than a crash loop, so no opt-in flag is required.

The scheduler SHALL NOT be able to fire while the container host is not running Docker. This limitation SHALL be documented rather than worked around; `catch_up` is its mitigation.

#### Scenario: stack starts with no schedule configured

- **WHEN** `docker compose up` runs on a machine with no `schedule.json`
- **THEN** the `scheduler` service starts, reports itself idle, and neither exits nor restarts in a loop

#### Scenario: scheduler waits for the schema

- **WHEN** the stack starts from an empty database
- **THEN** the scheduler does not start until `bootstrap` has completed successfully, so `schedule_state` exists before the first poll

### Requirement: A run records that it started, and an interrupted run is reconciled

The scheduler SHALL record that a run is in progress **before** invoking the chain, and SHALL overwrite that record with the terminal outcome when the chain finishes. A reader SHALL therefore be able to tell a run that is still executing from one that has finished, without consulting container logs. Recording only the outcome makes a long run indistinguishable from no run at all for its entire duration, which is how a run that started on time gets misread as a run that was caught up late.

Recording the start SHALL NOT require a schema change. `schedule_state.last_status` is unconstrained text, and `last_run_at` SHALL carry the start instant until the terminal write replaces it with the finish instant.

Consuming the slot and recording the start SHALL be one write. They are one decision — this slot is being spent on this run — and splitting them across two statements creates a window in which a slot is advanced with no run on record. That state is unrecoverable rather than merely brief: reconciliation looks for an in-progress record and finds none, the panel goes on reporting the previous run, and the day's run is skipped with nothing anywhere saying so. Seeding a slot without running it remains a separate write, because there no run is beginning.

A process that dies mid-run leaves an in-progress record with nothing left to overwrite it. The scheduler SHALL reconcile such a record at startup, recording the run as failed with an error naming the cause, rather than reporting a run that will never finish as still running. It SHALL NOT be given a status of its own: the row holds one run per job and is overwritten by the next, so a distinct value could never be counted over time, and the error line already distinguishes a process that died from a workflow that raised. Reconciliation SHALL happen at startup only: within a single process the poll loop executes jobs inline on one thread, so an in-progress record that process observes is genuinely in progress.

#### Scenario: a long run is visible while it runs

- **WHEN** the chain has been executing for twenty minutes
- **THEN** the `schedule_state` row reports the run as in progress, with the instant it started

#### Scenario: the outcome replaces the in-progress record

- **WHEN** the chain finishes successfully
- **THEN** the row reports success and the finish instant, with no in-progress record left behind

#### Scenario: a killed run does not stay in progress forever

- **WHEN** the container is killed mid-run and the scheduler starts again
- **THEN** the row left in progress is recorded as failed, with an error saying the process exited mid-run, and is not reported as a run still executing

#### Scenario: startup leaves a finished run alone

- **WHEN** the scheduler starts and the row records a previous run as succeeded or failed
- **THEN** reconciliation changes nothing

#### Scenario: a consumed slot always carries a run

- **WHEN** the scheduler consumes a due slot and the process dies before the chain produces anything
- **THEN** the row records both the new slot and a run in progress, so startup reconciliation reports the run as failed rather than leaving the previous run's outcome standing over a slot that was silently skipped

### Requirement: A malformed boolean in the schedule file is fatal

`enabled` and `catch_up` SHALL be read as JSON booleans. An absent field SHALL default to false, and a present field of any other type SHALL raise, naming the field. They SHALL NOT be coerced.

Coercion is not a neutral convenience here: `bool("false")` is `True`, and this file is hand-editable by design, so a quoted `"false"` written by an operator switching the schedule off would leave it on — on the only path in the system that spends model tokens with nobody watching. This matches how the same reader already treats a malformed time, which it rejects even while the schedule is disabled.

The dashboard's reader SHALL remain forgiving, and this SHALL NOT be read as a contradiction: the settings page renders on every route, so raising there would remove the panel an operator would use to repair the file.

#### Scenario: a quoted false does not switch the schedule on

- **WHEN** `schedule.json` holds `"enabled": "false"`
- **THEN** the pipeline-side reader raises, naming the field, rather than reading it as enabled

#### Scenario: an absent flag is still false

- **WHEN** `schedule.json` omits `catch_up`
- **THEN** the schedule reads as catch-up disabled, without error

