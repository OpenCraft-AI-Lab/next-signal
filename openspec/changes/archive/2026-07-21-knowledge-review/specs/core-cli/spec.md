## MODIFIED Requirements

### Requirement: `paca knowledge` subcommand group manages ingestion and GBrain

The `paca knowledge` subcommand group SHALL expose: `ingest <value>` (route a URL or staged local file through the knowledge-ingest pipeline, with `--ingest/--no-ingest` to control whether the clean markdown is imported into GBrain, `--category` to pin the destination taxonomy path and skip auto-classification, and `--progress` to emit one JSON event per pipeline step to stdout followed by the final JSON result); `gbrain-search <query> [--limit N]` (search GBrain through the local CLI bridge and print JSON results); `gbrain-ingest <path>` (import a markdown file or directory into GBrain through the local CLI bridge and print the JSON result); `init-test-gbrain [--home PATH]` (initialize an isolated local GBrain PGLite database under `state/test-gbrain` by default, for integration tests); and `review` (reconcile the wiki against `knowledge_reviews` — enroll docs with no row, unenroll rows whose file is gone — and print the counts of docs enrolled, unenrolled, and currently due; no flags, no LLM call, since the review card reuses each doc's frontmatter summary).

#### Scenario: operator ingests a URL

- **WHEN** the operator runs `paca knowledge ingest https://example.com/article`
- **THEN** the CLI runs the knowledge-ingest pipeline and prints the JSON result, importing into GBrain unless `--no-ingest` is passed

#### Scenario: progress events stream as JSONL

- **WHEN** the operator runs `paca knowledge ingest <value> --progress`
- **THEN** the CLI writes one JSON event per pipeline step to stdout, followed by a final JSON result line, forming valid JSONL

#### Scenario: operator searches GBrain from the CLI

- **WHEN** the operator runs `paca knowledge gbrain-search "topic" --limit 5`
- **THEN** the CLI prints the search results as indented JSON

#### Scenario: operator reconciles review enrollment

- **WHEN** the operator runs `paca knowledge review`
- **THEN** the CLI enrolls wiki docs that have no review row, unenrolls rows whose file is gone, and prints the enrolled, unenrolled, and due counts
