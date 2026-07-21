## MODIFIED Requirements

### Requirement: `paca info-radar analyze` runs the analysis pipeline

`paca info-radar analyze [--limit N] [--source NAME] [--locale zh|en]` SHALL run the two-tier info-radar-analysis pipeline over unseen `radar_items`, optionally capped to `N` items and/or restricted to one collector source, generating analysis output in the given locale (default `en`), and print the resulting counters.

#### Scenario: operator runs analysis with a limit

- **WHEN** the operator runs `paca info-radar analyze --limit 20`
- **THEN** the CLI processes at most 20 unseen items and prints `info-radar analyze: <counter>=<value> ...`

#### Scenario: operator runs analysis in English

- **WHEN** the operator runs `paca info-radar analyze --locale en`
- **THEN** the CLI runs the pipeline with `locale="en"`, and persisted analyses are generated in English and tagged `locale='en'`

#### Scenario: locale defaults to English

- **WHEN** the operator runs `paca info-radar analyze` with no `--locale`
- **THEN** the pipeline runs with `locale="en"`
