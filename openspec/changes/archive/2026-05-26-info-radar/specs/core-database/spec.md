## MODIFIED Requirements

### Requirement: Business tables use raw psycopg connections

Code that touches our business tables (`job_runs`, `scheduled_jobs`, `portfolio_tickers`, `seen_news`, `radar_items`) SHALL use short-lived `psycopg.connect(database_url())` connections. SQLAlchemy or async engines are not used for these tables.

#### Scenario: scheduler writes a job_run

- **WHEN** the scheduler dispatcher records a run
- **THEN** it opens a synchronous psycopg connection, writes one row, and closes it

#### Scenario: info-radar collector upserts radar_items

- **WHEN** the info-radar collector persists a batch of parsed items
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (source, source_id) DO NOTHING` for each item, and closes the connection

## ADDED Requirements

### Requirement: `radar_items` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `radar_items` with columns `id BIGSERIAL PRIMARY KEY`, `source TEXT NOT NULL`, `source_id TEXT NOT NULL`, `url TEXT`, `title TEXT NOT NULL`, `excerpt TEXT`, `published_at TIMESTAMPTZ`, `fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `seen_at TIMESTAMPTZ`, `payload JSONB NOT NULL`, `UNIQUE (source, source_id)`. It SHALL also create `radar_items_fetched_at_idx` on `fetched_at` and `radar_items_unseen_idx` on `fetched_at WHERE seen_at IS NULL`.

#### Scenario: fresh bootstrap creates the table

- **WHEN** the operator runs `uv run python scripts/bootstrap_db.py` against an empty database
- **THEN** `radar_items` exists with the documented columns, unique constraint, and both indexes
