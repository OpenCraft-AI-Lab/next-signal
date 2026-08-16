## MODIFIED Requirements

### Requirement: `next-signal doctor` self-checks the environment

`next-signal doctor` SHALL verify `.env` configuration (including whether
`OMLX_BASE_URL` is set — this checks the env var is configured, not that the
endpoint is reachable), the presence of each required credential in the
credential store, Postgres reachability, the presence of every registered tool,
the GBrain CLI / service health, and the folocli authentication (`FOLO_TOKEN`
present in the store and `folocli whoami` returns `ok: true`), reporting each
check as ✓ or ✗.

Credential checks SHALL report presence only, never any part of a value, and
SHALL direct the operator to the dashboard settings page rather than to `.env`.

#### Scenario: missing key reported

- **WHEN** `ANTHROPIC_API_KEY` is absent from the credential store
- **THEN** `next-signal doctor` reports a ✗ for the corresponding check, points
  at the settings page, and exits non-zero

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
