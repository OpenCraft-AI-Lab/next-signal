## RENAMED Requirements

- FROM: `### Requirement: `paca knowledge review` reconciles the wiki`
- TO: `### Requirement: `next-signal knowledge review` reconciles the wiki`

## MODIFIED Requirements

### Requirement: Reconciliation is explicit and refuses to act on an empty wiki

`next-signal knowledge review` SHALL walk the wiki, insert seeded rows for docs with no existing row, and delete rows whose `doc_path` no longer exists on disk. Reconciliation SHALL be idempotent. If the wiki root does not exist, is unreadable, or contains no markdown documents, it SHALL abort with a `RuntimeError` **without deleting any rows** — an empty tree is treated as a misconfiguration, not as evidence that every doc was deleted. Review state MUST NOT be written during dashboard page rendering.

#### Scenario: sync enrolls only new docs

- **WHEN** sync runs against a wiki where 3 of 40 docs have no review row
- **THEN** exactly 3 rows are inserted, seeded per the fast-forward rule, and the other 37 are unchanged

#### Scenario: repeat sync is a no-op

- **WHEN** sync runs twice with no wiki change in between
- **THEN** the second run inserts and deletes nothing

#### Scenario: missing wiki root does not wipe state

- **WHEN** sync runs while `WIKI_DIR` points at a missing or empty directory
- **THEN** it raises `RuntimeError` and no `knowledge_reviews` row is deleted

#### Scenario: deleted doc is unenrolled

- **WHEN** a doc's markdown file has been removed and sync runs against an otherwise populated wiki
- **THEN** its review row is deleted

### Requirement: `next-signal knowledge review` reconciles the wiki

`next-signal knowledge review` SHALL reconcile the wiki against `knowledge_reviews` — enrolling docs with no row (seeded per the fast-forward rule) and unenrolling rows whose file is gone — and print the number of docs enrolled, unenrolled, and currently due. It takes no flags and makes no LLM call.

#### Scenario: review reconciles and reports counts

- **WHEN** the operator runs `next-signal knowledge review` against a wiki with new and removed docs
- **THEN** new docs are enrolled, removed docs are unenrolled, and the command prints the enrolled, unenrolled, and due counts
