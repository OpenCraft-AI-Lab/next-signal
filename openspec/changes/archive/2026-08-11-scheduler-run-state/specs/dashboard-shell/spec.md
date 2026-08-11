## MODIFIED Requirements

### Requirement: The settings page owns the unattended run schedule

The settings page SHALL carry a section, visually separated from the sections around it, that owns the wall-clock schedule specified by `core-schedule`. It SHALL expose three controls — whether the schedule is enabled, the daily times, and whether a missed run is caught up — SHALL state the zone those times fire in without offering to change it, and SHALL read back the state of the most recent run.

The times SHALL be editable as a list, added and removed one row at a time, since the schedule is a set of daily times rather than a single one. A newly added row SHALL be a draft: it SHALL NOT be written until it holds a time and commits. The last remaining time SHALL NOT be removable — an enabled schedule with nothing to fire is not a reachable state, and the enable control is how the schedule is stopped. Adding a row SHALL choose the first hour not already taken, and SHALL do nothing once every hour is; a search for a free value SHALL be bounded by the values it can return.

Writes SHALL go to `~/.next-signal/schedule.json` through a server action, atomically, mirroring how the content-language setting writes its own file. The section SHALL NOT write on render.

The time control SHALL express a wall-clock time of day and nothing else, so that every value the file can hold is a value the page can display.

The timezone SHALL be displayed, not chosen: the section SHALL name the zone `core-schedule` resolves from `INFO_RADAR_TIMEZONE` and say where it is set, and SHALL NOT offer a control that records a zone of its own. The same value fixes radar day grouping and review due dates, so a schedule carrying its own zone would fire at 08:00 in one zone while its results were filed under a day boundary drawn in another. A stored zone that steers nothing is worse than none: its only observable effect is the warning that it has no effect.

The section SHALL display the next time a slot comes round, and SHALL compute it in the zone the scheduler resolves rather than the browser's. A next-run stated in a zone that decides nothing is confidently wrong, and it is the one value on this page an operator would act on without checking.

The times and catch-up controls SHALL be hidden while the schedule is disabled, since neither has meaning then.

The section SHALL state, in its hint text, that catch-up applies only to runs that were genuinely missed — including one missed while the machine was asleep — and that changing the schedule never triggers a run for a time that has just passed. This distinction is not discoverable from the controls themselves.

The run read-back SHALL come from the `schedule_state` row via the dashboard's existing Postgres pool, rendered with the existing relative-time helper, and SHALL distinguish four states: never run, in progress, succeeded, and failed. When the last run failed, the recorded error SHALL be reachable from the section rather than only from container logs.

While a run is in progress the section SHALL say so and SHALL show how long it has been running. A run of this chain can last far longer than an operator expects it to, and a section that shows only the previous run's outcome for that whole window reads as though nothing is happening — or, worse, as though the run that later appears was triggered late. Any status that is neither in progress nor success SHALL read as a failure, so a run nobody finished is never displayed as one that did.

The section SHALL reuse existing UI primitives rather than introducing new ones, so it inherits the page's visual language and incurs no `/design` catalogue addition.

Reads SHALL be forgiving in the same way, and for the same reason, as the content-language reader: a missing, corrupt, or invalid `schedule.json` SHALL render the section as disabled and log, never raise, so the page that would fix the file still renders. The pipeline-side reader SHALL continue to raise.

#### Scenario: operator schedules a daily run

- **WHEN** the operator enables the schedule and sets the time to 08:00
- **THEN** `~/.next-signal/schedule.json` is written atomically with `enabled: true` and `at: ["08:00"]`, and the running scheduler observes it on its next poll

#### Scenario: disabled schedule hides its details

- **WHEN** the schedule is disabled
- **THEN** the times, timezone line, and catch-up control are not rendered, and only the enable control and the section's hint remain

#### Scenario: the zone is stated rather than offered

- **WHEN** the operator opens an enabled schedule
- **THEN** the section shows the zone `core-schedule` resolves as read-only text, names the environment variable that sets it, offers no way to record a different one, and states the next run in that same zone

#### Scenario: adding a time terminates when every hour is taken

- **WHEN** the operator adds times until all twenty-four hours are occupied and adds once more
- **THEN** nothing is added and the page remains responsive

#### Scenario: last run is reported

- **WHEN** the most recent scheduled run failed
- **THEN** the section reports the failure and its time, and the recorded error text is reachable from the section

#### Scenario: a run in progress is reported as running

- **WHEN** the operator opens `/settings` while the chain has been executing for twenty minutes
- **THEN** the section reports that a run is in progress and how long it has been running, rather than reporting the previous run's outcome

#### Scenario: an interrupted run does not read as a success

- **WHEN** the most recent run was interrupted by the container being killed
- **THEN** the section reports it as a failure rather than as a completed run, with the recorded error explaining that the process exited mid-run

#### Scenario: never-run schedule reads as such

- **WHEN** a schedule is enabled but has not yet reached its first slot
- **THEN** the section reports that no run has happened yet, rather than showing an empty or zeroed timestamp

#### Scenario: unreadable schedule file does not break the settings page

- **WHEN** `~/.next-signal/schedule.json` is corrupt or holds an invalid time, and `/settings` is rendered
- **THEN** the section renders as disabled, the error is logged, and no page render fails

#### Scenario: rendering the page does not write the schedule

- **WHEN** the operator opens `/settings` without changing anything
- **THEN** no write to `~/.next-signal/schedule.json` occurs
