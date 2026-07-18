## MODIFIED Requirements

### Requirement: `paca doctor` self-checks the environment

`paca doctor` SHALL verify `.env` configuration, OMLX endpoint reachability, Postgres reachability, the presence of every registered tool, and the GBrain CLI / service health, reporting each check as ✓ or ✗.

#### Scenario: missing key reported

- **WHEN** `ANTHROPIC_API_KEY` is unset
- **THEN** `paca doctor` reports a ✗ for the corresponding check and exits non-zero

#### Scenario: GBrain CLI absent

- **WHEN** the `gbrain` CLI is not on PATH
- **THEN** `paca doctor` reports a ✗ for the GBrain check and explains how to install it
