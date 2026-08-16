# core-credentials Specification

## Purpose

Holds every provider credential next-signal uses in one user-state file that the
dashboard can write and every process reads at call time, so a deployment is
configured entirely from the browser and a credential change reaches a running
container without recreating it.

## Requirements

### Requirement: One credential store owns every provider credential

The system SHALL persist provider credentials in exactly one file,
`$NEXT_SIGNAL_STATE_DIR/secrets.json` (`/state/secrets.json` in a container), as
a flat JSON object mapping a credential name to its string value.

The credentials the system resolves by name SHALL be `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `OMLX_API_KEY`,
`GITHUB_TOKEN`, and `FOLO_TOKEN`. Names match the environment variables they
replace because child processes require the literal string.

The store SHALL NOT be limited to those names: an operator-defined
OpenAI-compatible embedding endpoint names its own credential through
`embedding.json`, so any name valid there SHALL be storable here. Names SHALL be
validated against the same pattern that file already enforces, so a name one
accepts the other accepts.

An absent file SHALL read as an empty store, since a fresh install has no
credentials and that is a valid state. A file that is present but unreadable,
not a JSON object, or holds a non-string value SHALL raise `RuntimeError`
naming the file — the same loud-failure rule the other state files follow.

System connection configuration — `DATABASE_URL`, `GBRAIN_*`, `POSTGRES_*`,
`*_BIN` paths, and CLI version pins — SHALL NOT move into the store.

#### Scenario: fresh install has no store

- **WHEN** no `secrets.json` exists and a credential is requested
- **THEN** the store reads as empty and the caller raises a missing-credential
  error naming the credential and pointing at the settings page

#### Scenario: malformed store fails loud

- **WHEN** `secrets.json` exists but does not parse as a JSON object of strings
- **THEN** reading it raises `RuntimeError` naming the file, rather than
  degrading to an empty store

### Requirement: Credentials are written atomically and readable only by the owner

A write SHALL publish the complete file in one atomic replacement, so a
concurrent reader observes either the previous contents or the new contents and
never a partial file. Concurrent writes SHALL NOT collide on a shared temporary
path.

On POSIX filesystems the file SHALL be created with mode `0600`. This guarantee
is scoped to the Linux container, which is the supported deployment; Windows
hosts map the mode onto ACLs only nominally, and the specification does not
claim owner-only access there.

#### Scenario: reader never sees a partial write

- **WHEN** a save is in flight while another process reads the store
- **THEN** the reader observes either the complete previous contents or the
  complete new contents

#### Scenario: stored file is owner-only in the container

- **WHEN** `secrets.json` is written inside the Linux container
- **THEN** its mode is `0600`

### Requirement: Credentials resolve at call time and never from the environment

Every credential SHALL be read from the store at the point of use. No credential
SHALL be read from a process environment variable, materialized into
`os.environ`, or captured at import time.

There SHALL be no fallback to an environment variable when the store lacks a
credential, and no migration or import path from a previously configured
environment. A missing credential SHALL raise an error naming the credential and
directing the operator to the settings page.

Because resolution happens at call time against a file on the shared state
volume, a credential saved by the dashboard SHALL be observed by the scheduler
and by newly spawned CLI processes without restarting or recreating any service.

#### Scenario: a saved credential reaches a running service

- **WHEN** a credential is saved in the dashboard while the scheduler container
  is running
- **THEN** the next job in that scheduler uses the new value without a restart
  or `docker compose up --force-recreate`

#### Scenario: an environment variable is not a credential source

- **WHEN** a credential name is set in the process environment but absent from
  the store
- **THEN** the system behaves as though the credential is unset and raises

### Requirement: Child processes receive credentials only when named

Credentials required by an external program SHALL be supplied through an
environment built for that one subprocess, naming the credentials that program
needs. The calling process's own environment SHALL NOT be modified.

A credential absent from the store SHALL be omitted from the child environment
rather than passed as an empty value, because a third-party program's handling
of an empty variable is not ours to define.

#### Scenario: only named credentials reach the child

- **WHEN** a subprocess is spawned with a child environment naming one
  credential
- **THEN** that credential is present in the child and no other credential is

#### Scenario: spawning does not leak into the parent

- **WHEN** a child environment carrying credentials is built and used
- **THEN** the parent process's own environment is unchanged afterwards

### Requirement: Credential values never leave the server

No credential value SHALL be sent to a browser, written to a log, or included in
an error message, diagnostic output, or exception text. Interfaces that report
configuration state SHALL expose only whether a credential is present.

No masked or partial rendering of a credential — including a last-four-character
preview — SHALL be produced.

#### Scenario: presence is reported without the value

- **WHEN** an interface reports whether a credential is configured
- **THEN** it emits only a boolean, and the value appears nowhere in the response

#### Scenario: failures name the credential, not its value

- **WHEN** a provider call fails because a credential is wrong
- **THEN** the error names the credential and contains no part of its value
