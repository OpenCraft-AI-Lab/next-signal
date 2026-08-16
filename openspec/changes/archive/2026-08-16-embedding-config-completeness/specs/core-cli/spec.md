## MODIFIED Requirements

### Requirement: `next-signal doctor` self-checks the environment

`next-signal doctor` SHALL verify `.env` system connection configuration, the
presence of each required credential in the credential store, the local model
endpoints recorded in user state (checking that they are configured, not that
they are reachable), Postgres reachability, the presence of every registered
tool, the GBrain CLI / service health, and the folocli authentication
(`FOLO_TOKEN` present in the store and `folocli whoami` returns `ok: true`),
reporting each check as ✓ or ✗.

`OMLX_BASE_URL` SHALL NOT be checked, because no part of the system reads it.
The local chat endpoint SHALL be reported from engine preferences and the
embedding endpoint from embedding preferences, since they are separately
configured.

Credential checks SHALL report presence only, never any part of a value, and
SHALL direct the operator to the dashboard settings page rather than to `.env`.
Endpoint checks SHALL do the same.

#### Scenario: missing key reported

- **WHEN** `ANTHROPIC_API_KEY` is absent from the credential store
- **THEN** `next-signal doctor` reports a ✗ for the corresponding check, points
  at the settings page, and exits non-zero

#### Scenario: endpoints are read from user state

- **WHEN** the local chat and embedding endpoints are recorded in user state
- **THEN** `next-signal doctor` reports each from its own state file and reads
  no endpoint from the process environment

#### Scenario: environment does not satisfy an endpoint check

- **WHEN** `OMLX_BASE_URL` is set in the process environment but no endpoint is
  recorded in user state
- **THEN** `next-signal doctor` reports the endpoint as unconfigured

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
