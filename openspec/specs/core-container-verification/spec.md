# core-container-verification

The contract the containerized stack offers to anything verifying against it: which source paths are live, which commands are free of model calls, how each service is reached, and what counts as evidence.

## Purpose

Runtime and end-to-end verification happens in containers, not on the host. That only produces trustworthy results if the verifier can tell whether the container is running the code under test — `/app` is image-baked, so an edit to `src/` followed by an immediate `docker compose exec` silently verifies the previous code. These requirements pin the facts a verifier depends on, so a pass means what it claims and so verifying plumbing does not incur model cost.
## Requirements

### Requirement: Source visibility contract

The containerized stack SHALL make explicit which host paths are live inside a
running container and which are captured at image build time, so that anything
verifying a change can tell whether the container is running the code under test.

`/wiki`, `/wiki-raw` (bind mounts) and `/state` (named volume) SHALL be live.
`/app` — containing `src/`, `configs/`, `prompts/`, `scripts/`, and
`dashboard/` — SHALL be image-baked and MUST NOT be assumed live. `tests/`,
`docs/`, and `openspec/` SHALL be excluded from the build context entirely.

Because `/app` is image-baked, each app service has its own writable layer, and a
write under `/app` in one container SHALL NOT be visible in another. Runtime files
that any service must both write and share — including the runtime goals file —
SHALL therefore live under `/state`, never under `/app/configs`.

The host sources for `/wiki` and `/wiki-raw` SHALL default to repo-relative
directories when `WIKI_DIR` and `WIKI_RAW_DIR` are unset or empty, so the stack
starts against an unedited `.env`. These defaults SHALL be expressed as bind-mount
sources with an explicit relative prefix, because Compose interprets a source
without one as a named volume — which would present an empty wiki rather than
failing. The defaults are consumed by Compose only: the in-container `WIKI_DIR` and
`WIKI_RAW_DIR` values SHALL remain explicitly set, so the application contract that
an unset wiki variable raises loudly is unaffected.

The supported platform for this default is Docker Desktop on macOS and Windows,
whose file-sharing layer maps ownership of a directory the daemon creates. On
native Linux Docker Engine the daemon creates a missing bind source root-owned;
the stack still runs, but host-side edits require a `chown` first. That
limitation SHALL be documented rather than automated around, because every
automated remedy reintroduces either a `.env` variable or committed placeholder
directories.

#### Scenario: Editing application source

- **WHEN** a host edit is made under `src/`, `configs/`, `prompts/`, or `dashboard/`
- **THEN** the running container continues to serve the previous code
- **AND** the edit is only observable after `docker compose build` followed by
  `docker compose up -d <service>`

#### Scenario: Editing wiki content

- **WHEN** a host edit is made under the directory bound to `/wiki`
- **THEN** the change is visible inside the running container immediately
- **AND** no rebuild or recreate is required

#### Scenario: Editing excluded directories

- **WHEN** a host edit is made under `tests/`, `docs/`, or `openspec/`
- **THEN** the image build cache is not invalidated
- **AND** no rebuild is required because the content never enters the image

#### Scenario: Writes under /app do not cross containers

- **WHEN** a file is written under `/app` inside the `dashboard` container
- **THEN** that file is absent in the `scheduler` container
- **AND** it is discarded by the next `docker compose build`

#### Scenario: Shared runtime state crosses containers

- **WHEN** a file under `/state` is written by one app service
- **THEN** every other app service reads the same content without a rebuild or
  recreate

#### Scenario: Stack starts with an unedited .env

- **WHEN** `docker compose up` runs with `WIKI_DIR` and `WIKI_RAW_DIR` unset or
  empty
- **THEN** the stack starts and `/wiki` and `/wiki-raw` resolve to repo-relative
  bind mounts rather than named volumes

### Requirement: The stack starts with no `.env` file present

Compose SHALL treat `.env` as optional, so `docker compose up` succeeds on a
fresh clone where the file has never been created. Every value Compose reads
from it SHALL have a default, and no application credential SHALL be sourced
from it.

This completes the first-run contract: the previous requirement is that the
stack starts against an *unedited* `.env`; this one is that it starts against no
`.env` at all, which is what a user who never opens a text editor actually has.

The contract SHALL hold on a **first-time state volume with an empty credential
store**, not only on a volume that a previous run already initialised. No
bootstrap step SHALL require a credential to be present, because the store is
written by the dashboard and the dashboard cannot start until bootstrap has
completed — a bootstrap that needs a credential makes the first run
unreachable by construction.

A bootstrap step whose initialisation needs a credential SHALL be skipped
entirely, leaving that capability uninitialised and reported as unavailable,
rather than failing or substituting a reduced initialisation that cannot
afterwards be completed.

Credentials SHALL reach the containers through the shared state volume rather
than through the container environment, so adding one SHALL NOT require
`docker compose up -d --force-recreate`.

#### Scenario: Fresh clone with no dotenv

- **WHEN** `docker compose up` runs in a working tree containing no `.env` file
- **THEN** the stack starts, with wiki mounts and Postgres settings resolving to
  their defaults

#### Scenario: First-time volume with an empty credential store

- **WHEN** `docker compose up` runs against a state volume that has never been
  initialised and a credential store that holds nothing
- **THEN** bootstrap completes successfully, and the dashboard and scheduler
  both start

#### Scenario: Credentials cross containers without a recreate

- **WHEN** a credential is written to `/state/secrets.json` by one app service
- **THEN** every other app service resolves it on its next use, with no rebuild,
  restart, or recreate

#### Scenario: Container environment carries no credential

- **WHEN** the environment of a running app container is inspected
- **THEN** it contains no provider credential, and the system still authenticates
  to providers

### Requirement: Image currency after build

A completed image build SHALL NOT change which image a running container uses.
Anything verifying against the stack MUST recreate the container to pick up a
newly built image, and MUST be able to detect the stale state before trusting a
verification result.

#### Scenario: Build without recreate

- **WHEN** `docker compose build <service>` completes successfully
- **THEN** the running container still references the previously built image ID
- **AND** comparing `docker image inspect` against `docker inspect <container>`
  reveals the mismatch

#### Scenario: Recreating onto the new image

- **WHEN** `docker compose up -d <service>` is run after a build
- **THEN** the container is recreated and its image ID matches the current image

#### Scenario: Restart does not re-read env_file

- **WHEN** `docker compose restart <service>` is run after `.env` changes
- **THEN** the container ID is unchanged and the previous environment persists
- **AND** picking up `.env` requires `docker compose up -d --force-recreate`

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

### Requirement: Service access surface

Each service SHALL have one documented access path for inspection. Postgres
SHALL NOT be published to the host, so database inspection MUST go through the
`postgres` service container.

#### Scenario: Inspecting the database

- **WHEN** the database is inspected via `docker compose exec -T postgres psql`
- **THEN** both `-U <user>` and `-d next_signal` must be supplied
- **AND** omitting the database name fails because psql defaults to a database
  named after the user, which does not exist

#### Scenario: Reaching Postgres from the host

- **WHEN** a host process attempts to connect to `localhost:5432`
- **THEN** the connection is refused because the port is not published

#### Scenario: Running a command against a one-shot service

- **WHEN** `docker compose exec` targets the exited `bootstrap` service
- **THEN** the command fails with `service "bootstrap" is not running`
- **AND** `docker compose run --rm` must be used instead, or the command run
  against `dashboard`, which shares the same image

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
optional under the active deployment profile, or when they report configuration
an operator has not completed yet.

A freshly started stack that nobody has configured SHALL be expected to exit
non-zero. Unset model credentials, an unselected embedder, and an uninitialised
GBrain are the normal first-run state, not defects in the stack.

#### Scenario: Cloud-only profile

- **WHEN** `next-signal doctor` runs in a container with no local endpoint
  configured and no embedder selected
- **THEN** it exits non-zero because unset model keys and the unselected
  embedder report ✗
- **AND** the stack is nonetheless healthy if `DATABASE_URL`, Postgres,
  configured agents, and registered tools all report ✔

#### Scenario: An unselected embedder is a first-run state

- **WHEN** a fresh stack has never had an embedder selected
- **THEN** the embedder check reports ✗ naming the unselected state and the
  stack is still considered correctly started

#### Scenario: An uninitialised GBrain is a first-run state

- **WHEN** a first-time stack has started and no GBrain brain has been
  initialised
- **THEN** the GBrain check reports it as uninitialised and names knowledge
  search as unavailable, and the stack is still considered correctly started

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

### Requirement: Test execution boundary

The runtime image SHALL NOT carry the test suite or a test runner. Unit tests
SHALL run on the host; the container is for runtime and end-to-end verification
only.

#### Scenario: Attempting to run tests in the container

- **WHEN** `pytest` is invoked inside the app container
- **THEN** it fails because neither the runner nor `tests/` is present
- **AND** the suite must be run on the host via `uv run pytest`
