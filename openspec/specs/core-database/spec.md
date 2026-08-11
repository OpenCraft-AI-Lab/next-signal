# core-database

Postgres + pgvector for both agno-managed state and our own business tables. Two strict connection paths.

## Purpose

agno owns sessions, memory, knowledge, and traces. We own the info-radar business tables. Mixing the two paths leads to contention and shape mismatches, so they must stay separated.
## Requirements
### Requirement: agno tables go through the singleton `PostgresDb`

Code that touches agno-managed tables (sessions, memory, knowledge, traces) SHALL acquire the database via `next_signal.core.db.get_db()`. Direct construction of `agno.db.PostgresDb` is prohibited.

#### Scenario: agno tables are auto-provisioned

- **WHEN** the AgentOS app starts with a configured `DATABASE_URL`
- **THEN** agno provisions its own tables; no application code defines or migrates them

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

### Requirement: SQLAlchemy URL adapter rewrites scheme

`next_signal.core.db.database_url(for_sqlalchemy=True)` SHALL rewrite the URL scheme to use the psycopg v3 driver (`postgresql+psycopg://`).

#### Scenario: agno consumes the SQLAlchemy URL

- **WHEN** agno requests the SQLAlchemy URL
- **THEN** the returned URL forces the psycopg v3 dialect; the v2 driver is never used

### Requirement: `radar_items` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `radar_items` with columns `id BIGSERIAL PRIMARY KEY`, `source TEXT NOT NULL`, `source_id TEXT NOT NULL`, `url TEXT`, `title TEXT NOT NULL`, `excerpt TEXT`, `published_at TIMESTAMPTZ`, `fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `seen_at TIMESTAMPTZ`, `payload JSONB NOT NULL`, `UNIQUE (source, source_id)`. It SHALL also create `radar_items_fetched_at_idx` on `fetched_at` and `radar_items_unseen_idx` on `fetched_at WHERE seen_at IS NULL`.

#### Scenario: fresh bootstrap creates the table

- **WHEN** the operator runs `uv run python scripts/bootstrap_db.py` against an empty database
- **THEN** `radar_items` exists with the documented columns, unique constraint, and both indexes

### Requirement: `radar_pushed_topics` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `radar_pushed_topics` with columns
`id BIGSERIAL PRIMARY KEY`, `topic_summary TEXT NOT NULL`,
`embedding vector(1024) NOT NULL`, `embedder TEXT NOT NULL`,
`item_ids JSONB NOT NULL`, `first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()`,
and `last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

`embedder` holds the stable vector-space identity captured in the
`core-embedding` resolved snapshot. Cosine search SHALL first restrict rows to
one identity. The fixed vector width is a contract enforced by `core-embedding`,
so provider switches do not alter the vector column.

The table's former mixed-space IVFFlat index SHALL NOT be provisioned. Bootstrap
SHALL run `DROP INDEX IF EXISTS radar_pushed_topics_embedding_idx` for upgraded
databases and SHALL create `radar_pushed_topics_embedder_idx` on `embedder`.
At the table's current scale, the dedup gate performs exact cosine ordering over
the selected identity's rows; an approximate index spanning multiple vector
spaces would let unrelated rows affect candidate generation and recall.

Because the table predates provenance and the historical model was
operator-configurable, bootstrap SHALL add the column idempotently with a
temporary `legacy:unknown` default, then drop that default. Existing rows remain
stored but no active provider searches them automatically. Bootstrap SHALL NOT
guess that they came from the shipped default model. A future insert omitting
`embedder` SHALL fail loudly.

`next_signal.core.db.BUSINESS_TABLE_COLUMNS["radar_pushed_topics"]` SHALL include
`embedder`, so doctor reports a database that has not run the migration.

#### Scenario: fresh bootstrap creates provider-scoped search support

- **WHEN** bootstrap runs against an empty database
- **THEN** the table includes `embedder`, the B-tree embedder index exists, and
  no mixed-space IVFFlat index exists

#### Scenario: existing history is preserved without guessed provenance

- **WHEN** bootstrap runs against a table that predates `embedder`
- **THEN** every historical row reads `legacy:unknown`, no row is deleted or
  rewritten, and the column carries no default afterwards

#### Scenario: an insert omitting provenance fails

- **WHEN** code inserts a topic without `embedder`
- **THEN** the NOT NULL constraint fails rather than mislabelling its vector

#### Scenario: bootstrap removes the old mixed-space index

- **WHEN** an upgraded database still has `radar_pushed_topics_embedding_idx`
- **THEN** bootstrap drops it idempotently and retains the vector data

#### Scenario: an un-migrated database is reported

- **WHEN** current code sees a live table without `embedder`
- **THEN** doctor reports the missing column before the pipeline runs

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

### Requirement: `knowledge_reviews` table is provisioned by bootstrap

`scripts/bootstrap_db.py` SHALL create `knowledge_reviews` with columns `id BIGSERIAL PRIMARY KEY`, `doc_path TEXT NOT NULL UNIQUE` (wiki-root-relative path, the same identity used by the ingest manifest), `captured_at DATE NOT NULL`, `stage INTEGER NOT NULL DEFAULT 0`, `next_due_at DATE` (`NULL` means retired past the final stage), `last_reviewed_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. It SHALL also create `knowledge_reviews_due_idx` on `next_due_at WHERE next_due_at IS NOT NULL`, supporting the due-selection query. The card body reuses the doc's frontmatter `summary`, so the row carries no generated-text columns.

The table SHALL hold no foreign keys — the wiki is a filesystem tree, not a table, and reconciliation is what keeps the two consistent.

#### Scenario: bootstrap provisions the table

- **WHEN** the operator runs `uv run python scripts/bootstrap_db.py` against an empty database
- **THEN** `knowledge_reviews` exists with the documented columns, the unique constraint on `doc_path`, and the partial due index

#### Scenario: bootstrap is safe to re-run

- **WHEN** `scripts/bootstrap_db.py` runs against a database that already has `knowledge_reviews`
- **THEN** the statement is a no-op and existing review rows and stages are preserved

### Requirement: `radar_eval_*` tables are development-only and not bootstrap-provisioned

`scripts/radar_eval.py` SHALL create its own three tables — `radar_eval_cases`, `radar_eval_runs`, `radar_eval_results` — via its `init` subcommand. `scripts/bootstrap_db.py` MUST NOT create them. They exist to measure prompt changes offline and carry no runtime behaviour, so a production deployment has no reason to hold them.

Like the business tables, they SHALL be reached through short-lived `psycopg.connect(database_url())` connections.

`radar_eval_cases` holds the hand-labelled expectation per item (`label_set`, `radar_item_id` referencing `radar_items` with `ON DELETE CASCADE`, `bucket`, `expect_verdict`, `expect_min`, `expect_max`, `rationale`) plus a frozen snapshot of the article `content` and `content_status`, unique on `(label_set, radar_item_id)`. Snapshotting content is what makes a variant comparison attributable to the prompt rather than to whether the fetch succeeded that day.

`radar_eval_runs` holds one row per invocation, including `prompt_digest` — a hash of both radar prompts plus `goals.yaml` — so a set of numbers can always be traced to the exact text that produced it.

`radar_eval_results` holds one row per `(run_id, case_id, repeat_idx)`, unique on that triple, so repeated runs of the same item are retained rather than overwritten. Retention is required because the scoring agent is sampled, not deterministic.

#### Scenario: bootstrap does not create the eval tables

- **WHEN** `scripts/bootstrap_db.py` runs against an empty database
- **THEN** the `radar_items`, `radar_analyses`, `radar_pushed_topics`, `radar_recaps`, and `knowledge_reviews` tables exist and no `radar_eval_*` table is created

#### Scenario: repeated evaluation of one item is retained

- **WHEN** the eval harness scores the same case three times within one run
- **THEN** three `radar_eval_results` rows exist for that case, distinguished by `repeat_idx`, and none has overwritten another

#### Scenario: deleting a radar_items row cascades to its eval case

- **WHEN** the 30-day sweep deletes a `radar_items` row referenced by a `radar_eval_cases` row
- **THEN** the eval case row is deleted along with it via `ON DELETE CASCADE`

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

