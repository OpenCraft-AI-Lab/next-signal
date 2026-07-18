## ADDED Requirements

### Requirement: Source descriptors live in a single YAML file

`paca/collectors/info_radar/` SHALL load source descriptors from `configs/info_radar/sources.yaml`. Each entry MUST declare `name` (unique), `enabled`, `cli` (with `argv` or `argv_template`, and `timeout_sec`), and `parser` (a registered parser name).

#### Scenario: enabled flag controls inclusion

- **WHEN** a source entry has `enabled: false`
- **THEN** the runner skips it and does not invoke its CLI

#### Scenario: unknown parser fails fast

- **WHEN** a source references a `parser:` name that is not in the `PARSERS` registry
- **THEN** the runner raises a `RuntimeError` at config load time, before any CLI is invoked

### Requirement: Parser registry exposes named parser functions

`paca/collectors/info_radar/parsers/__init__.py` SHALL export `PARSERS: dict[str, Callable[[str, str], list[RadarItem]]]`. Each parser MUST take the CLI's stdout and the source name, and return a list of `RadarItem`. Parsers MUST NOT perform any database I/O.

#### Scenario: parser returns RadarItem list

- **WHEN** the runner invokes a registered parser with stdout from its source's CLI
- **THEN** the parser returns a list of `RadarItem` instances or raises `RuntimeError` on schema mismatch

### Requirement: RadarItem contract

`paca.collectors.info_radar.schema.RadarItem` SHALL be a frozen dataclass with fields `source_id: str`, `title: str`, `url: str | None`, `excerpt: str | None`, `published_at: datetime | None`, and `payload: dict`. Parsers MUST populate `source_id` and `title`; other fields MAY be `None`.

#### Scenario: parser omits optional fields

- **WHEN** a source's upstream record has no `url`
- **THEN** the parser SHALL set `RadarItem.url = None` rather than fabricate or omit the field

### Requirement: Source-level dedup via Postgres unique constraint

The `radar_items` table SHALL declare `UNIQUE (source, source_id)`. The runner SHALL insert items with `INSERT ... ON CONFLICT (source, source_id) DO NOTHING`. The runner MUST NOT pre-query to decide whether to insert.

#### Scenario: re-pulling the same source returns no duplicates

- **WHEN** the runner pulls the same source twice with no new upstream items
- **THEN** the second pull writes zero new rows to `radar_items`

### Requirement: Folo posture is "ignore unread state"

Folo source descriptors MUST NOT pass `--unread-only` and MUST NOT call any `folocli entry mark-read` / `mark-all-read` subcommand. Folo's read/unread state belongs to the operator.

#### Scenario: collector leaves Folo state untouched

- **WHEN** the collector pulls a Folo source
- **THEN** the operator's unread count in the Folo app is unchanged

### Requirement: 30-day retention enforced at write and read

The runner SHALL `DELETE FROM radar_items WHERE fetched_at < now() - interval '30 days'` after every successful source pull (best-effort; failure logs but does not abort the pull). All query helpers in `paca/collectors/info_radar/store.py` SHALL include `fetched_at > now() - interval '30 days'` in their WHERE clause.

#### Scenario: items older than 30 days are removed

- **WHEN** the runner completes a pull and a row's `fetched_at` is 31 days ago
- **THEN** the sweep removes the row before the runner returns

#### Scenario: query helper hides expired rows even without sweep

- **WHEN** a query helper runs while expired rows still exist on disk
- **THEN** expired rows are filtered out by the WHERE clause

### Requirement: Per-source failure isolation

If a source's CLI exits non-zero, times out, or its parser raises, the runner SHALL log the failure, record it in the per-run summary, and continue with remaining sources. The runner SHALL exit non-zero only if every enabled source failed.

#### Scenario: one source fails, others succeed

- **WHEN** the folo source's CLI returns a non-zero exit and the zhihu source succeeds
- **THEN** the runner writes zhihu items, logs the folo failure, and exits zero

#### Scenario: every source fails

- **WHEN** every enabled source fails
- **THEN** the runner exits non-zero and surfaces each failure in stderr

### Requirement: Scheduler entry uses thin workflow shell

`paca/workflows/info_radar_pull.py` SHALL define an `InfoRadarPullWorkflow` class registered like any other workflow. Its only responsibility is to call `paca.collectors.info_radar.runner.run_all()` and return a summary. The scheduler schema is not modified.

#### Scenario: launchd-triggered pull

- **WHEN** the scheduler fires the `info_radar_pull` job
- **THEN** the workflow shell invokes the collector and persists items without involving any LLM
