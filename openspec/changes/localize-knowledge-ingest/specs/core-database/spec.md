## ADDED Requirements

### Requirement: `knowledge_tag_labels` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `knowledge_tag_labels` with columns `tag TEXT NOT NULL`, `locale TEXT NOT NULL` (`'zh'` | `'en'`), `label TEXT NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, and `PRIMARY KEY (tag, locale)`. This table is a display-alias translation memory: it maps a canonical English tag key to its localized display label per locale, populated once per unique `(tag, locale)` pair at ingest and read at render time. It is one of our business tables and SHALL be reached via short-lived `psycopg.connect(database_url())` connections. Provisioning SHALL be idempotent via `CREATE TABLE IF NOT EXISTS`.

#### Scenario: table created with the documented shape

- **WHEN** `scripts/bootstrap_db.py` runs
- **THEN** `knowledge_tag_labels` exists with the `(tag, locale)` primary key and the documented columns

#### Scenario: bootstrap is idempotent

- **WHEN** `scripts/bootstrap_db.py` is run twice
- **THEN** both runs succeed and the table exists exactly once

#### Scenario: label upsert is keyed on (tag, locale)

- **WHEN** a label already exists for `(multimodal, zh)` and the pipeline ensures labels again for that pair
- **THEN** no duplicate row is created and the existing label is reused
