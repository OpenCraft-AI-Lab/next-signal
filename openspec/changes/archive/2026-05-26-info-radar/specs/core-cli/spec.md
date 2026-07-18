## ADDED Requirements

### Requirement: `paca info-radar pull` invokes the collector

`paca info-radar pull [--source NAME]` SHALL load `configs/info_radar/sources.yaml`, run every enabled source (or only the named one), persist results to `radar_items`, and print a per-source summary. Exit code is zero unless every enabled source fails.

#### Scenario: operator pulls all sources

- **WHEN** the operator runs `paca info-radar pull`
- **THEN** the CLI invokes each enabled source's CLI, writes new items, and prints one line per source with the count written

#### Scenario: operator pulls one source

- **WHEN** the operator runs `paca info-radar pull --source folo_articles_ai`
- **THEN** the CLI invokes only that source and ignores others

### Requirement: `paca info-radar sweep` deletes expired rows

`paca info-radar sweep` SHALL run the 30-day retention `DELETE` against `radar_items` and report the number of rows removed.

#### Scenario: standalone sweep

- **WHEN** the operator runs `paca info-radar sweep`
- **THEN** the CLI prints the rows-removed count and exits zero, even if no rows were eligible

## MODIFIED Requirements

### Requirement: `paca doctor` self-checks the environment

`paca doctor` SHALL verify `.env` configuration, OMLX endpoint reachability, Postgres reachability, the presence of every registered tool, the GBrain CLI / service health, and the folocli authentication (`FOLO_TOKEN` set and `folocli whoami` returns `ok: true`), reporting each check as ✓ or ✗.

#### Scenario: missing key reported

- **WHEN** `ANTHROPIC_API_KEY` is unset
- **THEN** `paca doctor` reports a ✗ for the corresponding check and exits non-zero

#### Scenario: GBrain CLI absent

- **WHEN** the `gbrain` CLI is not on PATH
- **THEN** `paca doctor` reports a ✗ for the GBrain check and explains how to install it

#### Scenario: folocli not authenticated

- **WHEN** `FOLO_TOKEN` is unset and `folocli whoami` returns `ok: false`
- **THEN** `paca doctor` reports a ✗ for the folocli check and points to `folo login` or `FOLO_TOKEN`
