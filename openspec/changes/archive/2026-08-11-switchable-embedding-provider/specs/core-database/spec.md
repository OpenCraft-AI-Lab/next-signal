## MODIFIED Requirements

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
