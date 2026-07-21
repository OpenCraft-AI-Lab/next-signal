## ADDED Requirements

### Requirement: `paca info-radar recap` generates a range recap

`paca info-radar recap --since YYYY-MM-DD --until YYYY-MM-DD [--min-score N] [--novel-only] [--regenerate]` SHALL run the info-radar-recap workflow over the requested range and quality gate, and print the resulting headline plus one line per theme with its citation count. Without `--regenerate`, a request whose recap already exists in `status='done'` SHALL print the cached recap and make no LLM call. With `--regenerate`, the recap SHALL be recomputed and the stored row replaced. Both `--since` and `--until` are required; an inverted or unparseable range SHALL exit non-zero without invoking the agent. A range in which no item clears the quality gate SHALL print an explicit empty-result message and exit zero.

#### Scenario: operator generates a weekly recap

- **WHEN** the operator runs `paca info-radar recap --since 2026-07-13 --until 2026-07-19`
- **THEN** the CLI selects kept analyses in that local-date range, generates the recap, persists it, and prints the headline followed by each theme title and its citation count

#### Scenario: repeat invocation is served from cache

- **WHEN** the operator re-runs the same `paca info-radar recap` command for a range already recapped with `status='done'`
- **THEN** the CLI prints the stored recap and makes no LLM call

#### Scenario: regeneration forces recompute

- **WHEN** the operator runs the same command with `--regenerate`
- **THEN** the recap is recomputed and the existing row for that key is replaced rather than duplicated

#### Scenario: empty range exits cleanly

- **WHEN** the operator requests a recap for a range where no item clears the quality gate
- **THEN** the CLI prints an explicit empty-result message, writes no row, and exits zero

#### Scenario: inverted range is rejected

- **WHEN** the operator runs `paca info-radar recap --since 2026-07-19 --until 2026-07-13`
- **THEN** the CLI exits non-zero reporting the invalid range, and no agent is invoked
