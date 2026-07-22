## ADDED Requirements

### Requirement: `knowledge_reviews` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `knowledge_reviews` with columns `id BIGSERIAL PRIMARY KEY`, `doc_path TEXT NOT NULL UNIQUE` (wiki-root-relative path, the same identity used by the ingest manifest), `captured_at DATE NOT NULL`, `stage INTEGER NOT NULL DEFAULT 0`, `next_due_at DATE` (`NULL` means retired past the final stage), `last_reviewed_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. It SHALL also create `knowledge_reviews_due_idx` on `next_due_at WHERE next_due_at IS NOT NULL`, supporting the due-selection query. The card body reuses the doc's frontmatter `summary`, so the row carries no generated-text columns.

The table SHALL hold no foreign keys — the wiki is a filesystem tree, not a table, and reconciliation is what keeps the two consistent.

#### Scenario: bootstrap provisions the table

- **WHEN** the operator runs `uv run python scripts/bootstrap_db.py` against an empty database
- **THEN** `knowledge_reviews` exists with the documented columns, the unique constraint on `doc_path`, and the partial due index

#### Scenario: bootstrap is safe to re-run

- **WHEN** `scripts/bootstrap_db.py` runs against a database that already has `knowledge_reviews`
- **THEN** the statement is a no-op and existing review rows and stages are preserved

## MODIFIED Requirements

### Requirement: Business tables use raw psycopg connections

Code that touches our business tables (`radar_items`, `radar_analyses`, `radar_pushed_topics`, `radar_recaps`, `knowledge_reviews`) SHALL use short-lived `psycopg.connect(database_url())` connections. SQLAlchemy or async engines are not used for these tables.

#### Scenario: info-radar collector upserts radar_items

- **WHEN** the info-radar collector persists a batch of parsed items
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (source, source_id) DO NOTHING` for each item, and closes the connection

#### Scenario: recap workflow upserts radar_recaps

- **WHEN** the recap workflow persists or replaces a recap row
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (since, until, min_score, novel_only) DO UPDATE`, and closes the connection

#### Scenario: review sync enrolls wiki docs

- **WHEN** review reconciliation enrolls docs that have no review row
- **THEN** it opens a synchronous psycopg connection, inserts the seeded rows, and closes the connection
