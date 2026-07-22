# knowledge-review Specification

## Purpose

The read side of the knowledge base. Ingest files a doc and nothing ever brings it back; this layer resurfaces captured wiki docs along a fixed Ebbinghaus schedule so material decays out of memory less than it otherwise would. One `knowledge_reviews` row per doc, keyed by the wiki-relative `doc_path` (the same identity the ingest manifest uses), anchored to the doc's `captured_at`, with stages at 1, 3, 7, 15, 30, 60, and 120 days. The curve is deliberately fixed — no recall rating, no ease factor; "seen" is a single acknowledgement. Seeding and advancing both fast-forward past stages that have already elapsed, so enrolling an existing corpus (or reviewing late) never produces a backlog of overdue cards, and past the final stage a doc retires. Reconciliation against the filesystem is an explicit CLI step that refuses to act on a missing or empty wiki rather than reading "no files" as "everything deleted". The card body reuses the doc's own frontmatter `summary`, so the layer makes no LLM call and stores no generated text. It owns `knowledge_reviews` and reads wiki frontmatter; it never writes a wiki file.

## Requirements
### Requirement: Review state lives in Postgres, never in the wiki files

Review scheduling state SHALL be stored in the `knowledge_reviews` table, keyed by `doc_path` — the wiki-root-relative path, the same identity used by `knowledge_ingest_manifest.json` and the dashboard's document ids. The review layer MUST NOT write to any wiki markdown file, including frontmatter. Reading `captured_at` from frontmatter is the only interaction with wiki file contents that scheduling requires.

#### Scenario: advancing a review writes no wiki file

- **WHEN** a doc's review stage is advanced
- **THEN** only the `knowledge_reviews` row changes, and the doc's markdown file is byte-identical before and after

### Requirement: Curve stages are absolute offsets from `captured_at`

The schedule SHALL use fixed stage offsets of 1, 3, 7, 15, 30, 60, and 120 days. `next_due_at` SHALL be computed as `captured_at + STAGES[stage]` — always anchored to the capture date, never to `last_reviewed_at`. `captured_at` SHALL be resolved from frontmatter with the precedence `captured_at` → `updated_at` → `created_at` → file mtime, matching how the dashboard resolves a document's effective date.

#### Scenario: due date derives from capture, not from review time

- **WHEN** a doc captured on day 0 sits at stage 3 and is marked seen on day 25
- **THEN** its new `next_due_at` is computed from `captured_at` plus a stage offset, not from day 25

#### Scenario: frontmatter precedence is honored

- **WHEN** a doc has no `captured_at` but does have `updated_at` in frontmatter
- **THEN** `updated_at` is used as the anchor

### Requirement: Seeding and advancing both fast-forward past elapsed stages

When a doc is first enrolled, `stage` SHALL be set to the number of stage offsets that have already elapsed relative to `captured_at` — equivalently, the index of the first stage not yet elapsed. When a doc is marked seen, its new stage SHALL be `max(stage + 1, first-not-yet-elapsed-stage)`. Neither operation SHALL ever produce a `next_due_at` in the past.

#### Scenario: old doc enrolls near the end of the curve

- **WHEN** a doc captured 100 days ago is enrolled
- **THEN** it seeds to the stage whose offset is 120 days, with `next_due_at` 20 days in the future, and generates no overdue reviews

#### Scenario: fresh doc enrolls at the first stage

- **WHEN** a doc captured today is enrolled
- **THEN** its `next_due_at` is one day in the future and it is not due today

#### Scenario: late review does not cascade a backlog

- **WHEN** a card at the 15-day stage is marked seen on day 40
- **THEN** the doc advances past every stage already elapsed and its new `next_due_at` is in the future, rather than immediately presenting another overdue card

### Requirement: Docs retire past the final stage

Advancing beyond the 120-day stage SHALL set `next_due_at` to `NULL`. A row with `next_due_at IS NULL` SHALL NOT be selected as due.

#### Scenario: final review retires the doc

- **WHEN** a doc at the final stage is marked seen
- **THEN** its `next_due_at` becomes `NULL` and it no longer appears in any due selection

### Requirement: Reconciliation is explicit and refuses to act on an empty wiki

`paca knowledge review` SHALL walk the wiki, insert seeded rows for docs with no existing row, and delete rows whose `doc_path` no longer exists on disk. Reconciliation SHALL be idempotent. If the wiki root does not exist, is unreadable, or contains no markdown documents, it SHALL abort with a `RuntimeError` **without deleting any rows** — an empty tree is treated as a misconfiguration, not as evidence that every doc was deleted. Review state MUST NOT be written during dashboard page rendering.

#### Scenario: sync enrolls only new docs

- **WHEN** sync runs against a wiki where 3 of 40 docs have no review row
- **THEN** exactly 3 rows are inserted, seeded per the fast-forward rule, and the other 37 are unchanged

#### Scenario: repeat sync is a no-op

- **WHEN** sync runs twice with no wiki change in between
- **THEN** the second run inserts and deletes nothing

#### Scenario: missing wiki root does not wipe state

- **WHEN** sync runs while `PACA_WIKI_DIR` points at a missing or empty directory
- **THEN** it raises `RuntimeError` and no `knowledge_reviews` row is deleted

#### Scenario: deleted doc is unenrolled

- **WHEN** a doc's markdown file has been removed and sync runs against an otherwise populated wiki
- **THEN** its review row is deleted

### Requirement: The review card reuses the doc's frontmatter summary

The review card SHALL present the doc's existing frontmatter `summary` — the closing summary written to frontmatter and the `## 总结` section at ingest — rather than generating separate per-doc text. The review layer SHALL make no LLM call and SHALL store no generated text on the review row. When a doc has no frontmatter `summary` (e.g. a hand-created wiki file), the card SHALL fall back to the first prose paragraph of the body, and render title and schedule alone if neither exists.

#### Scenario: card shows the doc's own summary

- **WHEN** a due doc has a frontmatter `summary`
- **THEN** the card renders that summary, and no recall generation or LLM call occurs

#### Scenario: a doc without a summary falls back to its body

- **WHEN** a due doc has no frontmatter `summary`
- **THEN** the card renders the first prose paragraph of the body, or title and schedule alone if the body is empty

### Requirement: `paca knowledge review` reconciles the wiki

`paca knowledge review` SHALL reconcile the wiki against `knowledge_reviews` — enrolling docs with no row (seeded per the fast-forward rule) and unenrolling rows whose file is gone — and print the number of docs enrolled, unenrolled, and currently due. It takes no flags and makes no LLM call.

#### Scenario: review reconciles and reports counts

- **WHEN** the operator runs `paca knowledge review` against a wiki with new and removed docs
- **THEN** new docs are enrolled, removed docs are unenrolled, and the command prints the enrolled, unenrolled, and due counts

### Requirement: Due selection is local-day based and ordered by urgency

A doc SHALL be due when `next_due_at IS NOT NULL AND next_due_at <= <today>`, where today is the current date in the configured radar timezone, so review and radar agree on what "today" means. Due docs SHALL be ordered by `next_due_at` ascending, ties broken by `captured_at` ascending, so the longest-overdue material surfaces first.

#### Scenario: overdue docs sort ahead of just-due docs

- **WHEN** one doc has been due for 9 days and another became due today
- **THEN** the 9-day-overdue doc is ordered first

#### Scenario: future due dates are excluded

- **WHEN** a doc's `next_due_at` is tomorrow
- **THEN** it is not selected as due today
