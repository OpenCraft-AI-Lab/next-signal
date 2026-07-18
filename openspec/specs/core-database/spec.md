# core-database

Postgres + pgvector for both agno-managed state and our own business tables. Two strict connection paths.

## Purpose

agno owns sessions, memory, knowledge, and traces. We own scheduling/portfolio/news bookkeeping. Mixing the two paths leads to contention and shape mismatches, so they must stay separated.
## Requirements
### Requirement: agno tables go through the singleton `PostgresDb`

Code that touches agno-managed tables (sessions, memory, knowledge, traces) SHALL acquire the database via `paca.core.db.get_db()`. Direct construction of `agno.db.PostgresDb` is prohibited.

#### Scenario: agno tables are auto-provisioned

- **WHEN** the AgentOS app starts with a configured `DATABASE_URL`
- **THEN** agno provisions its own tables; no application code defines or migrates them

### Requirement: Business tables use raw psycopg connections

Code that touches our business tables (`job_runs`, `scheduled_jobs`, `portfolio_tickers`, `seen_news`, `radar_items`) SHALL use short-lived `psycopg.connect(database_url())` connections. SQLAlchemy or async engines are not used for these tables.

#### Scenario: scheduler writes a job_run

- **WHEN** the scheduler dispatcher records a run
- **THEN** it opens a synchronous psycopg connection, writes one row, and closes it

#### Scenario: info-radar collector upserts radar_items

- **WHEN** the info-radar collector persists a batch of parsed items
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (source, source_id) DO NOTHING` for each item, and closes the connection

### Requirement: SQLAlchemy URL adapter rewrites scheme

`paca.core.db.database_url(for_sqlalchemy=True)` SHALL rewrite the URL scheme to use the psycopg v3 driver (`postgresql+psycopg://`).

#### Scenario: agno consumes the SQLAlchemy URL

- **WHEN** agno requests the SQLAlchemy URL
- **THEN** the returned URL forces the psycopg v3 dialect; the v2 driver is never used

### Requirement: `radar_items` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `radar_items` with columns `id BIGSERIAL PRIMARY KEY`, `source TEXT NOT NULL`, `source_id TEXT NOT NULL`, `url TEXT`, `title TEXT NOT NULL`, `excerpt TEXT`, `published_at TIMESTAMPTZ`, `fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `seen_at TIMESTAMPTZ`, `payload JSONB NOT NULL`, `UNIQUE (source, source_id)`. It SHALL also create `radar_items_fetched_at_idx` on `fetched_at` and `radar_items_unseen_idx` on `fetched_at WHERE seen_at IS NULL`.

#### Scenario: fresh bootstrap creates the table

- **WHEN** the operator runs `uv run python scripts/bootstrap_db.py` against an empty database
- **THEN** `radar_items` exists with the documented columns, unique constraint, and both indexes

