## MODIFIED Requirements

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
