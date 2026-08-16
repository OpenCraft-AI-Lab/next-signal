## ADDED Requirements

### Requirement: The stack starts with no `.env` file present

Compose SHALL treat `.env` as optional, so `docker compose up` succeeds on a
fresh clone where the file has never been created. Every value Compose reads
from it SHALL have a default, and no application credential SHALL be sourced
from it.

This completes the first-run contract: the previous requirement is that the
stack starts against an *unedited* `.env`; this one is that it starts against no
`.env` at all, which is what a user who never opens a text editor actually has.

Credentials SHALL reach the containers through the shared state volume rather
than through the container environment, so adding one SHALL NOT require
`docker compose up -d --force-recreate`.

#### Scenario: Fresh clone with no dotenv

- **WHEN** `docker compose up` runs in a working tree containing no `.env` file
- **THEN** the stack starts, with wiki mounts and Postgres settings resolving to
  their defaults

#### Scenario: Credentials cross containers without a recreate

- **WHEN** a credential is written to `/state/secrets.json` by one app service
- **THEN** every other app service resolves it on its next use, with no rebuild,
  restart, or recreate

#### Scenario: Container environment carries no credential

- **WHEN** the environment of a running app container is inspected
- **THEN** it contains no provider credential, and the system still authenticates
  to providers
