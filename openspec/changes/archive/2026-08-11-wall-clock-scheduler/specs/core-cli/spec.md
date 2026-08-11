## ADDED Requirements

### Requirement: `next-signal schedule` runs the wall-clock scheduler

`next-signal schedule` SHALL run the scheduler poll loop in the foreground until interrupted. It is the command the `scheduler` container service runs, and it takes no flags — the schedule itself lives in `~/.next-signal/schedule.json`, not in argv, so that the dashboard and the operator edit one source of truth.

The command SHALL emit structured log lines to stdout on start (naming the resolved timezone and whether a schedule is configured), when a run begins and ends, and when a run fails. Because a container operator's only window into a long-running service is its log stream, a scheduler that runs silently SHALL be considered non-conforming.

#### Scenario: operator runs the scheduler

- **WHEN** the operator runs `next-signal schedule`
- **THEN** the loop starts, logs its resolved timezone and configured state, and stays in the foreground polling until interrupted

#### Scenario: scheduler starts with no schedule configured

- **WHEN** `next-signal schedule` starts and no schedule file exists
- **THEN** it logs that no schedule is configured, keeps polling, and exits non-zero only on an unrecoverable error, not on an absent schedule

#### Scenario: a failing run does not stop the command

- **WHEN** a scheduled chain raises during a run
- **THEN** the failure is logged at error level and the command keeps polling rather than exiting
