## MODIFIED Requirements

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
