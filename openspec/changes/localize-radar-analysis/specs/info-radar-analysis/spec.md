## ADDED Requirements

### Requirement: Analysis output language follows the request locale

The analysis pipeline SHALL accept a `locale` (one of `zh`, `en`; runtime default `en`) on `run()` and thread it unchanged through every stage. The generated language of tier-1 `reason`, tier-2 `summary`, and tier-2 `impact` SHALL be determined by this locale, NOT by the language of the goals block or the source article. Goals and article content MAY be in any language and are treated as input only; the locale fixes the OUTPUT language. dedup `reason` (internal) SHALL also follow the run locale.

#### Scenario: English locale over Chinese goals

- **WHEN** `run(locale="en")` processes an item and `configs/info_radar/goals.yaml` is written in Chinese
- **THEN** the persisted `summary` and `impact_md` are in English

#### Scenario: default locale is English

- **WHEN** `run()` is invoked with no `locale` argument
- **THEN** the pipeline behaves as `locale="en"` and generates English output

#### Scenario: locale does not gate item selection or dedup candidates

- **WHEN** a run with one locale processes items whose prior `radar_pushed_topics` were generated under a different locale
- **THEN** dedup ANN candidate retrieval is unaffected by locale (cross-language dedup is intended) and item selection still depends only on `seen_at IS NULL`

### Requirement: Locale selects a pure-language prompt variant per stage

Each analysis stage (`radar_tier1_filter`, `radar_tier2_impact`, `radar_dedup_judge`) SHALL build its agent with the run locale so that a pure-language prompt variant is selected for that locale. Each stage's prompt SHALL exist as a `zh` (Chinese-only prose and rubric) and an `en` (English-only prose and rubric) variant; a stage MUST NOT ship a single EN/CN-mixed prompt. The tier-1 drop-category **cue vocabulary** SHALL remain bilingual in both variants — each variant SHALL carry both Chinese and English cue literals rendered as idiomatic per-language equivalents (semantic match, not literal translation) — because either locale may score an article in the other language.

#### Scenario: stage builds the locale-matched prompt

- **WHEN** the tier-2 stage runs under `locale="en"`
- **THEN** it builds `radar_tier2_impact` with the English prompt variant, and the Chinese variant is not used

#### Scenario: tier-1 recognizes cross-language marketing cues

- **WHEN** the tier-1 stage runs under `locale="en"` and receives a Chinese vendor-PR item (e.g. `重磅发布` puff)
- **THEN** the English tier-1 variant still recognizes it as a drop category via the retained bilingual cue vocabulary, and emits its `reason` in English

### Requirement: Analysis rows record their generation locale

Every `radar_analyses` row written by the pipeline SHALL persist the run `locale` in a `locale` column, recording the language the row's content was generated in.

#### Scenario: kept item stores its locale

- **WHEN** `run(locale="en")` persists a `keep` analysis
- **THEN** the `radar_analyses` row has `locale='en'`

#### Scenario: dropped item stores its locale

- **WHEN** `run(locale="zh")` persists a tier-1 `drop`
- **THEN** the `radar_analyses` row has `locale='zh'`

## MODIFIED Requirements

### Requirement: Business tables and DDL

`scripts/bootstrap_db.py` SHALL provision `radar_analyses` and `radar_pushed_topics` tables with the columns described in design.md §D7 and §D8. The `embedding` column on `radar_pushed_topics` SHALL be `vector(1024)` and an `ivfflat` cosine index SHALL be created. ON DELETE CASCADE from `radar_items` to `radar_analyses` SHALL be configured. `radar_analyses` SHALL include a `locale` column recording the generation language of each row; the bootstrap SHALL add it via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS locale TEXT` so pre-existing deployments gain the column, and legacy rows SHALL be backfilled to `'zh'`.

#### Scenario: bootstrap is idempotent

- **WHEN** `scripts/bootstrap_db.py` is run twice
- **THEN** both runs succeed and the tables / indexes exist exactly once

#### Scenario: existing deployment gains the locale column

- **WHEN** `scripts/bootstrap_db.py` runs against a database whose `radar_analyses` table predates the `locale` column
- **THEN** the column is added via `ADD COLUMN IF NOT EXISTS` and existing rows are backfilled to `'zh'`

### Requirement: CLI surface

`paca info-radar analyze` SHALL be a Typer subcommand under the existing `info-radar` group. It SHALL accept `--limit N` (max items processed this run), `--source NAME` (restrict to a single collector source), and `--locale <zh|en>` (output language of generated analysis; default `en`). It SHALL print a one-line summary including the counters from the workflow return value.

#### Scenario: limit caps the batch

- **WHEN** `paca info-radar analyze --limit 5` is invoked and 20 unseen items exist
- **THEN** at most 5 items are processed, and the printed summary reflects counts that sum to ≤ 5

#### Scenario: locale flag sets the output language

- **WHEN** `paca info-radar analyze --locale en` is invoked
- **THEN** the pipeline runs with `locale="en"` and persisted analyses are in English with `locale='en'`

#### Scenario: locale defaults to English

- **WHEN** `paca info-radar analyze` is invoked with no `--locale`
- **THEN** the pipeline runs with `locale="en"`
