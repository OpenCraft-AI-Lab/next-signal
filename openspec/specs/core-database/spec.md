# core-database

Postgres + pgvector for both agno-managed state and our own business tables. Two strict connection paths.

## Purpose

agno owns sessions, memory, knowledge, and traces. We own the info-radar business tables. Mixing the two paths leads to contention and shape mismatches, so they must stay separated.
## Requirements
### Requirement: agno tables go through the singleton `PostgresDb`

Code that touches agno-managed tables (sessions, memory, knowledge, traces) SHALL acquire the database via `paca.core.db.get_db()`. Direct construction of `agno.db.PostgresDb` is prohibited.

#### Scenario: agno tables are auto-provisioned

- **WHEN** the AgentOS app starts with a configured `DATABASE_URL`
- **THEN** agno provisions its own tables; no application code defines or migrates them

### Requirement: Business tables use raw psycopg connections

Code that touches our business tables (`radar_items`, `radar_analyses`, `radar_pushed_topics`, `radar_recaps`) SHALL use short-lived `psycopg.connect(database_url())` connections. SQLAlchemy or async engines are not used for these tables.

#### Scenario: info-radar collector upserts radar_items

- **WHEN** the info-radar collector persists a batch of parsed items
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (source, source_id) DO NOTHING` for each item, and closes the connection

#### Scenario: recap workflow upserts radar_recaps

- **WHEN** the recap workflow persists or replaces a recap row
- **THEN** it opens a synchronous psycopg connection, runs `INSERT ... ON CONFLICT (since, until, min_score, novel_only) DO UPDATE`, and closes the connection

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

### Requirement: `radar_pushed_topics` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `radar_pushed_topics` with columns `id BIGSERIAL PRIMARY KEY`, `topic_summary TEXT NOT NULL`, `embedding vector(1024) NOT NULL`, `item_ids JSONB NOT NULL`, `first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()`. It SHALL also create an `ivfflat (embedding vector_cosine_ops)` index (`lists = 100`) for the dedup gate's approximate-nearest-neighbor lookup. The embedding dimension is fixed at 1024 to match the default `Qwen3-Embedding-0.6B-8bit` embedder profile; swapping embedders requires a column migration.

#### Scenario: fresh bootstrap creates the topics table

- **WHEN** the operator runs `uv run python scripts/bootstrap_db.py` against an empty database
- **THEN** `radar_pushed_topics` exists with the documented columns and the ivfflat cosine index

### Requirement: `radar_analyses` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `radar_analyses` with columns `id BIGSERIAL PRIMARY KEY`, `radar_item_id BIGINT NOT NULL REFERENCES radar_items(id) ON DELETE CASCADE`, `verdict TEXT NOT NULL` (`'drop'` | `'keep'`), `tier1_reason TEXT`, `summary TEXT`, `impact_md TEXT`, `score INTEGER`, `tags JSONB NOT NULL DEFAULT '[]'::jsonb`, `content_status TEXT` (`'full'` | `'fallback'` | `'error'` | `NULL`), `dedup_status TEXT` (`'novel'` | `'duplicate'` | `NULL`), `dedup_match_id BIGINT REFERENCES radar_pushed_topics(id) ON DELETE SET NULL`, `pushed_at TIMESTAMPTZ`, `analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `UNIQUE (radar_item_id)` (makes re-runs idempotent). `radar_item_id`'s `ON DELETE CASCADE` means the 30-day `radar_items` sweep also removes the corresponding analysis row. It SHALL also create `radar_analyses_unpushed_idx` on `analyzed_at WHERE verdict='keep' AND dedup_status='novel' AND pushed_at IS NULL`.

#### Scenario: fresh bootstrap creates the analyses table

- **WHEN** the operator runs `uv run python scripts/bootstrap_db.py` against an empty database
- **THEN** `radar_analyses` exists with the documented columns, the `radar_items` foreign key with `ON DELETE CASCADE`, the unique constraint, and the partial index

#### Scenario: sweeping a radar_items row cascades to its analysis

- **WHEN** the 30-day sweep deletes a `radar_items` row that has a corresponding `radar_analyses` row
- **THEN** the `radar_analyses` row is deleted along with it via `ON DELETE CASCADE`

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

