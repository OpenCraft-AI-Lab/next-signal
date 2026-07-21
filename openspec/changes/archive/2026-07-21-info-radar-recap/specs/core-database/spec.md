## ADDED Requirements

### Requirement: `radar_recaps` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `radar_recaps` with columns `id BIGSERIAL PRIMARY KEY`, `since DATE NOT NULL`, `until DATE NOT NULL`, `min_score INTEGER NOT NULL DEFAULT 0`, `novel_only BOOLEAN NOT NULL DEFAULT FALSE`, `status TEXT NOT NULL` (`'running'` | `'done'` | `'error'`), `headline TEXT`, `themes JSONB NOT NULL DEFAULT '[]'::jsonb`, `item_count INTEGER`, `considered_count INTEGER`, `max_analyzed_at TIMESTAMPTZ`, `error TEXT`, `generated_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `UNIQUE (since, until, min_score, novel_only)` (makes repeat requests idempotent and regeneration an in-place upsert).

The table SHALL NOT declare a foreign key to `radar_items`. Citation ids live inside the `themes` JSONB payload precisely so a recap survives the 30-day `radar_items` sweep — a recap is a point-in-time artifact and is expected to outlive its sources. Consumers SHALL render a citation whose source row no longer exists as plain text rather than a broken link.

#### Scenario: bootstrap provisions the table

- **WHEN** the operator runs `uv run python scripts/bootstrap_db.py` against an empty database
- **THEN** `radar_recaps` exists with the documented columns and the unique constraint on `(since, until, min_score, novel_only)`

#### Scenario: bootstrap is safe to re-run

- **WHEN** `scripts/bootstrap_db.py` runs against a database that already has `radar_recaps`
- **THEN** the statement is a no-op and existing recap rows are preserved

#### Scenario: sweeping a cited radar_items row leaves the recap intact

- **WHEN** the 30-day sweep deletes a `radar_items` row whose id appears in a stored recap's `themes` citations
- **THEN** the `radar_recaps` row is unaffected and its remaining content stays readable

## MODIFIED Requirements

### Requirement: Business tables use raw psycopg connections

Code that touches our business tables (`radar_items`, `radar_analyses`, `radar_pushed_topics`, `radar_recaps`) SHALL use short-lived `psycopg.connect(database_url())` connections. SQLAlchemy or async engines are not used for these tables.

#### Scenario: info-radar collector upserts radar_items

- **WHEN** the info-radar collector persists a batch of parsed items
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (source, source_id) DO NOTHING` for each item, and closes the connection

#### Scenario: recap workflow upserts radar_recaps

- **WHEN** the recap workflow persists or replaces a recap row
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (since, until, min_score, novel_only) DO UPDATE`, and closes the connection
