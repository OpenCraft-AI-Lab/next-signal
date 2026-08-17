## MODIFIED Requirements

### Requirement: `next-signal doctor` self-checks the environment

`next-signal doctor` SHALL verify `.env` system connection configuration, the
presence of each required credential in the credential store, **which engine
production stage jobs will resolve**, the local model endpoints recorded in
user state (checking that they are configured, not that they are reachable),
Postgres reachability, the presence of every registered tool, the GBrain CLI /
service health **and whether GBrain is initialised and able to embed**, and
the folocli authentication (`FOLO_TOKEN` present in the store and `folocli
whoami` returns `ok: true`), reporting each check as ✓ or ✗.

The engine check SHALL report an unselected engine distinctly from a selected
one, and its message SHALL state the consequence — every production stage job
(info-radar analyze, info-radar recap, knowledge ingest) will fail to start —
rather than describing it only as an error in the system.

`OMLX_BASE_URL` SHALL NOT be checked, because no part of the system reads it.
The local chat endpoint SHALL be reported from engine preferences and the
embedding endpoint from embedding preferences, since they are separately
configured.

GBrain readiness SHALL be reported as three distinct states, because collapsing
them hides a deployment that cannot search:

- **not initialised** — a failed check naming knowledge search as unavailable
  and naming the command that initialises GBrain. This is the expected state of
  a first-time stack, because bootstrap deliberately leaves GBrain
  uninitialised; it is reported so that it is visible rather than discovered
  when a search returns nothing.
- **initialised but not ready** — the selected embedding provider's credential
  is absent, so the brain exists but cannot embed. A failed check naming that
  provider's credential.
- **ready** — initialised with a model whose credential requirements are
  satisfied.

This check SHALL determine those states itself rather than delegating to the
external tool's own health command, which reports a healthy brain and exits zero
even when no brain exists.

Credential checks SHALL report presence only, never any part of a value, and
SHALL direct the operator to the dashboard settings page rather than to `.env`.
Endpoint checks SHALL do the same.

#### Scenario: missing key reported

- **WHEN** `DEEPSEEK_API_KEY` is absent from the credential store
- **THEN** `next-signal doctor` reports a ✗ for the corresponding check, points
  at the settings page, and exits non-zero

#### Scenario: no engine selected is reported

- **WHEN** `engine.json` records no primary engine
- **THEN** `next-signal doctor` reports a ✗ stating that production stage jobs
  cannot run, points at the settings page, and exits non-zero

#### Scenario: a selected engine is reported without a request

- **WHEN** `engine.json` records a primary engine
- **THEN** `next-signal doctor` reports it and its fallback, performing no
  provider call

#### Scenario: endpoints are read from user state

- **WHEN** the local chat and embedding endpoints are recorded in user state
- **THEN** `next-signal doctor` reports each from its own state file and reads
  no endpoint from the process environment

#### Scenario: environment does not satisfy an endpoint check

- **WHEN** `OMLX_BASE_URL` is set in the process environment but no endpoint is
  recorded in user state
- **THEN** `next-signal doctor` reports the endpoint as unconfigured

#### Scenario: an uninitialised GBrain is reported

- **WHEN** the GBrain CLI is reachable but no brain has been initialised
- **THEN** `next-signal doctor` reports a ✗ stating that knowledge search is
  unavailable and naming the command that initialises GBrain

#### Scenario: an initialised GBrain missing its provider credential is reported

- **WHEN** GBrain is initialised with an embedding model whose provider
  credential is absent from the store
- **THEN** `next-signal doctor` reports a ✗ naming that provider's credential,
  distinctly from the uninitialised state

#### Scenario: environment does not satisfy a credential check

- **WHEN** a credential is set in the process environment but absent from the
  credential store
- **THEN** `next-signal doctor` reports a ✗ for that credential

#### Scenario: GBrain CLI absent

- **WHEN** the `gbrain` CLI is not on PATH
- **THEN** `next-signal doctor` reports a ✗ for the GBrain check and explains how to install it

#### Scenario: folocli not authenticated

- **WHEN** `FOLO_TOKEN` is absent from the credential store
- **THEN** `next-signal doctor` reports a ✗ for the folocli check and points to
  the settings page, without suggesting `folo login`
