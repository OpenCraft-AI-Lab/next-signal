## MODIFIED Requirements

### Requirement: Model-call-free command set

The stack SHALL offer a documented set of commands that exercise the CLI, the
database, and the dashboard without invoking any local or remote model, so that
plumbing can be verified without incurring model cost.

`next-signal list`, `next-signal doctor`, `next-signal knowledge review`, `next-signal info-radar pull`,
`next-signal info-radar sweep`, and `next-signal info-radar subscriptions --json` SHALL be free
of model calls. `next-signal run-agent`, `next-signal knowledge ingest`,
`next-signal run-workflow knowledge_ingest`, `next-signal info-radar analyze`, and
`next-signal info-radar recap` SHALL be documented as incurring model calls.

#### Scenario: Verifying the collector path without model cost

- **WHEN** `next-signal info-radar pull` is run inside the container
- **THEN** it fetches from configured sources and writes `radar_items`
- **AND** no agent is constructed and no model endpoint is contacted
- **AND** re-running it reports items as skipped rather than duplicating rows

#### Scenario: Read-only dashboard surfaces

- **WHEN** any dashboard page or any `/api/radar/*` endpoint is requested
- **THEN** the response is served from the database or filesystem
- **AND** no model call is triggered by the request

### Requirement: Environment integrity under exec

Commands sent into a container SHALL preserve the image's configured `PATH`, so
that project executables resolve. Invocations MUST NOT use a login shell.

#### Scenario: Login shell erases the virtualenv

- **WHEN** a command is invoked via `sh -lc` inside the app container
- **THEN** `/app/.venv/bin` is dropped from `PATH` and `next-signal` fails to resolve

#### Scenario: Non-login shell preserves the virtualenv

- **WHEN** the same command is invoked via `sh -c`, or `next-signal` is exec'd directly
- **THEN** `PATH` retains `/app/.venv/bin` and `next-signal` resolves

### Requirement: Health-check exit code semantics

`next-signal doctor` SHALL report per-check status independently of its exit code. A
non-zero exit MUST NOT be read as stack failure when the failing checks are
optional under the active deployment profile.

#### Scenario: Cloud-only profile

- **WHEN** `next-signal doctor` runs in a container with no OMLX endpoint configured
- **THEN** it exits non-zero because `OMLX_BASE_URL` and unset model keys report ✗
- **AND** the stack is nonetheless healthy if `DATABASE_URL`, Postgres,
  configured agents, and registered tools all report ✔

### Requirement: Dashboard action observability

Dashboard-triggered work SHALL be treated as asynchronous. Server actions return
once the subprocess is spawned, not once it finishes, so confirmation MUST come
from the action log plus the resulting database state.

#### Scenario: Confirming a dashboard-triggered run

- **WHEN** a dashboard control spawns a `next-signal` subprocess
- **THEN** the action reports only that the work started
- **AND** progress is observable in the action log under the container's `$HOME`
- **AND** completion is confirmed by querying the table the work writes

#### Scenario: Action log does not survive recreate

- **WHEN** the dashboard container is recreated
- **THEN** the action log is lost because `$HOME` is not on a persistent volume
- **AND** durable evidence must be taken from the database instead
