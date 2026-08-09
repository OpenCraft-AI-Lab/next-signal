## RENAMED Requirements

- FROM: `### Requirement: paca doctor checks goals.yaml`
- TO: `### Requirement: next-signal doctor checks goals.yaml`

## MODIFIED Requirements

### Requirement: Goals declared in a single user-editable YAML

`next_signal/workflows/info_radar_analysis/` SHALL load goal descriptors from `configs/info_radar/goals.yaml`. The file MUST contain a top-level `goals:` list. Each entry MUST declare `name` (unique, kebab-case), `description`, `topics` (list of strings), and `keywords` (list of strings). Unknown top-level keys or unknown per-entry keys SHALL raise `RuntimeError` at load time. A missing or empty `goals.yaml` SHALL raise `RuntimeError` — the workflow MUST NOT fall back to an implicit default goal.

#### Scenario: missing goals.yaml aborts the run

- **WHEN** `next-signal info-radar analyze` runs and `configs/info_radar/goals.yaml` does not exist
- **THEN** the workflow raises `RuntimeError` referencing the missing path and exits non-zero before any LLM call

#### Scenario: duplicate goal names fail fast

- **WHEN** `goals.yaml` contains two entries with the same `name`
- **THEN** the loader raises `RuntimeError` mentioning the duplicate `name`

### Requirement: YouTube subtitle enrichment is opportunistic

When a tier-1-kept item's `payload.entries.url` is a YouTube watch URL or `payload.feeds.url` matches `rsshub://youtube/...`, the workflow SHALL attempt native subtitle extraction via `next_signal.integrations.info_radar.youtube_subs.fetch_captions(url)`. If captions are returned, they MUST be concatenated into the tier-2 input as additional context. If the helper raises or returns empty, the workflow MUST proceed without subtitles. Audio-transcription fallback is explicitly out of scope.

#### Scenario: no captions available falls through silently

- **WHEN** subtitle fetch raises or returns empty for a YouTube item
- **THEN** the workflow logs the absence and runs tier-2 on title+description without raising

### Requirement: CLI surface

`next-signal info-radar analyze` SHALL be a Typer subcommand under the existing `info-radar` group. It SHALL accept `--limit N` (max items processed this run) and `--source NAME` (restrict to a single collector source). It SHALL print a one-line summary including the counters from the workflow return value.

#### Scenario: limit caps the batch

- **WHEN** `next-signal info-radar analyze --limit 5` is invoked and 20 unseen items exist
- **THEN** at most 5 items are processed, and the printed summary reflects counts that sum to ≤ 5

### Requirement: Workflow entry is present and idempotent across runs

`configs/workflows/info_radar_analysis.yaml` SHALL set `expose.agent_os: false` and `extra.run_now: next_signal.workflows.info_radar_analysis:run`. How often it runs is operator-controlled and NOT a stable contract — the workflow's idempotency (`seen_at` gate plus `UNIQUE(radar_item_id)` on `radar_analyses`) SHALL make it safe to run at any frequency.

#### Scenario: manual run invokes the workflow

- **WHEN** `next-signal info-radar analyze` (or `next-signal run-workflow info_radar_analysis`) is invoked
- **THEN** it calls `next_signal.workflows.info_radar_analysis:run()` and processes unseen items

#### Scenario: running back-to-back produces no duplicate analyses

- **WHEN** two runs occur in quick succession with no collector pull between them
- **THEN** the second run processes zero items because all unseen items from the first run were marked `seen_at`

### Requirement: next-signal doctor checks goals.yaml

`next-signal doctor` SHALL include a `goals.yaml` check that reports OK with the goal count when the file exists and parses, and reports FAIL with the loader's error message otherwise. The check SHALL NOT invoke any LLM.

#### Scenario: missing goals.yaml fails the doctor check

- **WHEN** `next-signal doctor` runs and `configs/info_radar/goals.yaml` does not exist
- **THEN** the doctor output includes a FAIL line for the goals.yaml check
