## RENAMED Requirements

- FROM: `### Requirement: Dedup gate via pgvector ANN plus LLM judge`
- TO: `### Requirement: Dedup gate via provider-scoped pgvector search plus LLM judge`

## MODIFIED Requirements

### Requirement: Dedup gate via provider-scoped pgvector search plus LLM judge

For every tier-2 `keep` result, the workflow SHALL resolve one
`core-embedding` snapshot, embed the tier-2 summary with it, and carry the
snapshot's identity beside that vector through search and persistence. A live
settings re-read after embedding SHALL NOT determine the stored identity.

The workflow SHALL run an exact cosine search over
`radar_pushed_topics.embedding`, restricted first to rows whose `embedder`
equals the query vector's captured identity, limited to the top 5 candidates
within a configurable distance threshold (default 0.40). Rows from another
identity, including `legacy:unknown`, SHALL NOT participate in candidate
generation or be shown to the judge.

If candidates exist, the workflow SHALL invoke `radar_dedup_judge` with the new
summary and candidate summaries. A valid duplicate verdict SHALL set
`dedup_status='duplicate'` and `dedup_match_id`; a non-duplicate verdict or no
candidates SHALL set `dedup_status='novel'` and insert a new topic row containing
the exact vector and identity from the same resolved snapshot.

Changing selection parks post-migration rows under the previous identity and
switching back restores them. Pre-change `legacy:unknown` rows remain retained
but inactive unless an operator explicitly relabels them after independently
verifying their provenance.

#### Scenario: novel item stores its resolved identity

- **WHEN** provider-scoped search finds no candidate
- **THEN** the workflow stores a novel analysis and a topic row containing the
  summary, vector, captured identity, and item id

#### Scenario: duplicate item links to same-space topic

- **WHEN** same-identity candidates exist and the judge returns duplicate
- **THEN** the analysis links to the matched topic and appends the item id

#### Scenario: embedding failure remains conservative

- **WHEN** snapshot resolution or embedding raises
- **THEN** the workflow logs loudly, stores the analysis as novel, and inserts no
  topic row

#### Scenario: settings change cannot mislabel an in-flight vector

- **WHEN** provider A is resolved and state changes to B before topic insertion
- **THEN** the current item's search and insert still use identity A, while the
  next item resolves B

#### Scenario: another vector space does not affect candidate generation

- **WHEN** the table contains rows under identities A, B, and `legacy:unknown`
  and the query identity is B
- **THEN** exact distance ordering examines only B rows

#### Scenario: switching back restores post-migration memory

- **WHEN** the operator switches from A to B and later back to A
- **THEN** previously stored A rows become candidates again without re-embedding

### Requirement: Business tables and DDL

`scripts/bootstrap_db.py` SHALL provision `radar_analyses` and
`radar_pushed_topics` with the existing analysis columns plus
`radar_pushed_topics.embedder TEXT NOT NULL`. The embedding column SHALL remain
`vector(1024)`, whose width is enforced by `core-embedding`.

Bootstrap SHALL remove the former mixed-space IVFFlat index and create a normal
index on `embedder`. Existing rows that predate provenance SHALL be labelled
`legacy:unknown` without deleting or rewriting their vectors. The existing
`ON DELETE CASCADE` from `radar_items` to `radar_analyses` remains unchanged.

#### Scenario: bootstrap is idempotent

- **WHEN** bootstrap runs twice
- **THEN** both runs succeed with one embedder index, no old IVFFlat index, and
  unchanged topic rows

#### Scenario: DDL is stable across provider switches

- **WHEN** the active embedding provider changes
- **THEN** the vector column and indexes are not rebuilt and no row is deleted
