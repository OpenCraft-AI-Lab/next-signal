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

The credentials the system resolves by name SHALL be `DEEPSEEK_API_KEY`,
`RADAR_EMBEDDING_OPENAI_API_KEY`, `EMBEDDING_API_KEY`, `OPENAI_API_KEY`,
`VOYAGE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, and `FOLO_TOKEN`.
`RADAR_EMBEDDING_OPENAI_API_KEY` and `EMBEDDING_API_KEY` replace no environment
variable — the former names next-signal's own radar-dedup OpenAI credential,
distinct from the identically-behaved but differently-consumed knowledge-base
credential below; the latter names the credential an operator-defined
OpenAI-compatible embedding endpoint uses. `OPENAI_API_KEY`, `VOYAGE_API_KEY`,
and `GOOGLE_GENERATIVE_AI_API_KEY` name GBrain's own embedding-provider
credentials exactly as GBrain's subprocess reads them from its environment —
these are external, fixed names this system does not choose.

`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GITHUB_TOKEN`, and `OMLX_API_KEY` SHALL
NOT be members of this set. The first two have no feature in this system that
resolves them. The latter two are read with graceful-degradation semantics
only (anonymous GitHub access; unauthenticated local-server requests) and are
not required by any capability this system exposes through configuration.

The set of resolved names SHALL be closed. Every credential the system resolves
SHALL appear in that enumeration, so an interface that renders one control per
credential covers all of them and no configurable credential can exist without a
place to enter it. Names SHALL still be validated against a documented pattern.

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

#### Scenario: every resolved credential has an entry point

- **WHEN** an interface renders one control per credential the system resolves
- **THEN** every credential any feature can require is present in that list,
  including the one an OpenAI-compatible embedding endpoint uses

#### Scenario: the radar and knowledge OpenAI credentials are independent

- **WHEN** `RADAR_EMBEDDING_OPENAI_API_KEY` is saved and `OPENAI_API_KEY` is not
- **THEN** the radar dedup embedder resolves its credential successfully and
  GBrain's OpenAI provider still reports its own credential as absent

#### Scenario: a removed name renders no control

- **WHEN** the settings interface renders one control per credential in the
  resolved set
- **THEN** no control exists for `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`,
  `GITHUB_TOKEN`, or `OMLX_API_KEY`, since none is a member of that set

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

This requirement applies regardless of whether the spawning module itself
reads or names the credential in its own source. It SHALL also cover the case
where the *external program* reads a credential-shaped variable from its own
inherited environment — the spawning module may never mention that
credential's name at all, which means a grep for credential names does not
prove this requirement is met.

A subprocess spawn SHALL NOT be built by copying the calling process's whole
environment (for example Python's `os.environ.copy()` or Node's
`{...process.env}`) unmodified when the target program might read a
credential-shaped variable on its own. Omitting an explicit environment for a
spawn — letting the platform's default full inheritance apply — is conforming
only when the target program is verified to consume no credential; that
verification SHALL NOT be assumed from the spawning module's own source
containing no credential name.

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

#### Scenario: a third-party program reading its own credential is still scoped

- **WHEN** a spawned external program (not our code) reads a credential-shaped
  environment variable on its own, and the spawning module never names that
  credential anywhere in its source
- **THEN** the subprocess is still built through a child environment that
  strips every known credential name before re-adding only the ones the call
  site explicitly supplies, rather than through an unmodified copy of the
  calling process's environment

#### Scenario: an unscoped environment copy is a defect regardless of grep results

- **WHEN** a subprocess spawn is built with `os.environ.copy()` or
  `{...process.env}` and handed to an external program that can read a
  credential from its environment
- **THEN** the spawn does not conform to this requirement even though no
  credential name appears anywhere in the spawning module's source

### Requirement: Container bootstrap handles no credential

`scripts/container_bootstrap.sh` SHALL NOT read, inject, export, or otherwise
handle any provider credential. It runs before any credential can exist: the
store is written by the dashboard, and the dashboard does not start until
bootstrap has completed successfully.

A bootstrap step that would need a credential to initialise an external program
SHALL NOT perform that initialisation at all. It SHALL leave the program
uninitialised for an operator to complete later, and the dependent capability
SHALL be reported as unavailable until they do. It SHALL NOT branch on whether a
credential happens to be present, because a conditional path reintroduces
credential handling into a script that must not have any.

Bootstrap SHALL NOT substitute a reduced initialisation that avoids the
credential, where that reduced form cannot afterwards be completed. Such a form
is not a deferral but a permanent choice made before the operator can make it.

Steps that need no credential SHALL still run, so that deferral is scoped to the
initialisation itself rather than to everything near it. Maintaining an
already-initialised program — migrations and other no-credential upkeep — SHALL
continue to run on every boot.

This requirement exists because the shell script cannot use the Python
credential helpers, so a shell-side "mirror" of them drifts silently — which is
exactly how bootstrap came to inherit an environment that no longer holds the
credential it assumed. Removing the need is the durable fix; copying the
injection is not.

Bootstrap SHALL NOT later initialise a program it deferred. Doing so would
require reading a credential, which is the thing this requirement forbids.

#### Scenario: bootstrap succeeds against an empty store

- **WHEN** container bootstrap runs with no credential configured anywhere
- **THEN** every step completes and the script exits zero

#### Scenario: bootstrap does not consult the store

- **WHEN** container bootstrap runs with credentials present in the store
- **THEN** it behaves identically to a run with an empty store, and reads no
  credential

#### Scenario: an external program needing a credential is left uninitialised

- **WHEN** bootstrap reaches a step that would initialise an external program
  whose initialisation requires a credential
- **THEN** it performs no initialisation, exits zero, and the dependent
  capability is reported as unavailable rather than partially configured

#### Scenario: maintenance of an already-initialised program still runs

- **WHEN** container bootstrap runs against an external program that is already
  initialised
- **THEN** its no-credential maintenance steps run as before, unaffected by the
  deferral of first-time initialisation

### Requirement: An injected credential is scoped to the selected provider

Where a spawned external program can be pointed at any of several providers, the
credential injected into its environment SHALL be the one **the selected
provider** requires, resolved from the selection rather than hard-coded to a
single provider.

A selection naming a provider that requires no credential — a local or
self-hosted runner — SHALL be supported with no credential injected at all, and
SHALL NOT be blocked by the absence of an unrelated provider's key. This
requirement covers credential scoping only: a local provider's endpoint
(where to reach it) is separate from its credential (whether it needs one),
and configuring that endpoint is out of scope for this change — see
`proposal.md` Non-Goals.

Where the selected provider does require a credential and it is absent, the
failure SHALL name that provider's credential specifically, not a default one.

#### Scenario: the selected provider's credential is the one injected

- **WHEN** an external program is spawned for a provider whose credential
  differs from the default provider's
- **THEN** that provider's credential is injected and the default provider's is
  not

#### Scenario: a local provider needs no credential

- **WHEN** the selected provider is a local runner requiring only an endpoint
- **THEN** the spawn succeeds with no credential injected, against an empty
  credential store

#### Scenario: a missing credential names the right provider

- **WHEN** the selected provider requires a credential that is absent from the
  store
- **THEN** the error names that provider's credential and points at the
  dashboard settings page

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
