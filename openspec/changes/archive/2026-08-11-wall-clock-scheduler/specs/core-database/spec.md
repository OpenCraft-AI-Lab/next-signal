## MODIFIED Requirements

### Requirement: Business tables use raw psycopg connections

Code that touches our business tables (`radar_items`, `radar_analyses`, `radar_pushed_topics`, `radar_recaps`, `knowledge_reviews`, `schedule_state`) SHALL use short-lived `psycopg.connect(database_url())` connections. SQLAlchemy or async engines are not used for these tables.

#### Scenario: info-radar collector upserts radar_items

- **WHEN** the info-radar collector persists a batch of parsed items
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (source, source_id) DO NOTHING` for each item, and closes the connection

#### Scenario: recap workflow upserts radar_recaps

- **WHEN** the recap workflow persists or replaces a recap row
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (since, until, min_score, novel_only) DO UPDATE`, and closes the connection

#### Scenario: review sync enrolls wiki docs

- **WHEN** review reconciliation enrolls docs that have no review row
- **THEN** it opens a synchronous psycopg connection, inserts the seeded rows, and closes the connection

#### Scenario: scheduler advances a slot

- **WHEN** the scheduler seeds or advances a job's `last_slot_at`
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (job) DO UPDATE`, and closes the connection

## ADDED Requirements

### Requirement: `schedule_state` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `schedule_state` with columns `job TEXT PRIMARY KEY`, `last_slot_at TIMESTAMPTZ NOT NULL`, `last_run_at TIMESTAMPTZ`, `last_status TEXT` (`'ok'` | `'failed'` | `'running'` | `NULL`), and `last_error TEXT`. One row exists per scheduled job; the wall-clock scheduler ships a single job, `radar`.

`last_status` SHALL remain unconstrained text rather than an enum or a CHECK: `'running'` is written before a chain that can last an hour and overwritten when it ends, so the set of values is a scheduler concern that has already grown once. Readers are specified in `core-schedule` and `dashboard-shell`, not in the DDL.

The table carries no foreign keys and no indexes beyond the primary key: it holds at most a handful of rows and is only ever read by primary key or in full.

`last_slot_at` records the most recent scheduled instant already handled, not when execution occurred — the two differ whenever a run is caught up or the process was down. The distinction is normative; storing an execution timestamp here would break the missed-run model specified in `core-schedule`.

`schedule_state` SHALL be registered in `next_signal.core.db`'s business-table column contract, so `next-signal doctor` reports a drifted or missing table.

#### Scenario: bootstrap creates the table

- **WHEN** `scripts/bootstrap_db.py` runs against a fresh database
- **THEN** `schedule_state` exists with the documented columns and its primary key on `job`

#### Scenario: bootstrap is idempotent

- **WHEN** `scripts/bootstrap_db.py` runs against a database that already has `schedule_state`
- **THEN** it completes without error and leaves existing rows untouched

#### Scenario: doctor reports a missing table

- **WHEN** `next-signal doctor` runs against a database where `schedule_state` is absent
- **THEN** it reports the table among the unsatisfied business-table columns rather than passing silently
