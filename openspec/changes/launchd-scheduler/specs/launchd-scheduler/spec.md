## ADDED Requirements

### Requirement: launchd as the scheduling primitive

The scheduler SHALL use one macOS `launchd` plist per scheduled job (`StartCalendarInterval`) instead of an in-process timer; agno's built-in in-process scheduler MUST NOT be enabled.

#### Scenario: missed window catches up after wake

- **WHEN** the Mac is asleep at the scheduled trigger time
- **THEN** launchd fires the job at the next wake (per `StartCalendarInterval` semantics) and the dispatcher records a single run

### Requirement: Single dispatcher posts to AgentOS

A single `paca.scheduler.dispatcher` entry point SHALL be invoked by every plist; it reads the job config, POSTs to the AgentOS HTTP endpoint, writes one row to `job_runs` (status, started_at, finished_at, error), and triggers the notification helper on completion.

#### Scenario: dispatcher records both success and failure

- **WHEN** a job runs and either succeeds or fails
- **THEN** `job_runs` contains exactly one row for that run with the correct terminal status and duration

### Requirement: CLI manages plist lifecycle

`paca schedule install / list / remove / run-now` SHALL install, list, remove, and immediately fire scheduled jobs based on `configs/schedules.yaml`, and SHALL keep the `scheduled_jobs` Postgres table in sync with the YAML.

#### Scenario: install creates a launchd plist

- **WHEN** the operator runs `paca schedule install daily_portfolio_brief`
- **THEN** a plist is written under `~/Library/LaunchAgents/`, loaded with `launchctl bootstrap`, and a row is upserted into `scheduled_jobs`

### Requirement: Plists never contain secrets

The plist generator SHALL NOT embed API keys, tokens, or passwords. Secrets MUST be loaded by the dispatcher from `.env` at run time.

#### Scenario: secret is read at run time

- **WHEN** the dispatcher needs `ANTHROPIC_API_KEY`
- **THEN** it reads the variable from `.env` (or the shell environment); the plist contains only paths and arguments
