## ADDED Requirements

### Requirement: Knowledge ingest uses agent-led orchestration

The single-item knowledge ingest path SHALL be coordinated by an Agno workflow that calls deterministic tools for fetch, artifact editing, validation, wiki write, and optional GBrain ingest while preserving the existing JSON result shape.

#### Scenario: save result remains compatible

- **WHEN** the ingest workflow completes successfully for a supported input
- **THEN** the result includes `ok`, `source_type`, `category`, `markdown_path`, `raw_path`, `frontmatter`, and optional `ingest` fields with the same meaning as before

#### Scenario: manager uses ingest workflow

- **WHEN** the knowledge manager handles a user request to ingest a URL or staged file
- **THEN** it uses `knowledge_ingest_workflow` instead of calling low-level `gbrain_ingest` directly

### Requirement: Artifact editor owns clean body and frontmatter generation

The pipeline SHALL use a dedicated artifact editor agent to transform a fetched source packet into cleaned markdown plus frontmatter draft fields: `title`, `summary`, `tags`, `freshness`, and `related_queries`.

#### Scenario: orchestrator avoids full-body editing

- **WHEN** a fetched markdown packet is ready for content processing
- **THEN** the orchestrator passes the packet to the artifact editor agent and does not generate cleaned markdown or frontmatter itself

#### Scenario: editor output is structured

- **WHEN** the artifact editor returns a result
- **THEN** the result is parsed as structured data containing cleaned markdown and the required frontmatter draft fields

### Requirement: Deterministic validation gates artifact writes

Edited artifact output SHALL pass deterministic validation before any clean wiki markdown is written.

#### Scenario: transcript summary is rejected

- **WHEN** the source contains a transcript and the edited markdown removes the transcript section or compresses the body below the configured retention threshold
- **THEN** validation fails and the artifact is not written

#### Scenario: invalid frontmatter is rejected

- **WHEN** the artifact editor returns empty summary text, invalid freshness, or tags that do not match the required lowercase English tag format
- **THEN** validation fails and the artifact is not written

### Requirement: LLM editing failures fail loudly

The save path SHALL fail without writing a clean wiki artifact when the required artifact editor LLM call fails, returns unparsable output, or remains invalid after the configured validation retry. The pipeline MUST NOT generate deterministic fallback body or frontmatter content to complete the save.

#### Scenario: editor call unavailable

- **WHEN** the artifact editor agent cannot complete the required edit
- **THEN** the save operation raises a loud failure and no clean wiki artifact is written

#### Scenario: retry output remains invalid

- **WHEN** validation feedback is sent to the artifact editor and the retried output still fails validation
- **THEN** the save operation raises a loud failure instead of creating fallback markdown or frontmatter

### Requirement: GBrain ingest failure keeps written artifacts

The agent-led save path SHALL write the clean markdown artifact before optional GBrain ingest and SHALL fail loud on ingest failure without deleting or rolling back the artifact.

#### Scenario: GBrain CLI offline after write

- **WHEN** the clean markdown artifact has been written and the GBrain ingest tool fails
- **THEN** the saved markdown remains on disk and the final result raises a loud ingest error

### Requirement: Direct ingest and re-index share GBrain identity

Direct single-input ingest and wiki re-index SHALL ingest markdown files under the same GBrain-safe slug derived from the wiki-relative markdown path.

#### Scenario: direct ingest matches weekly re-index slug

- **WHEN** direct ingest writes `knowledge/example.md`
- **THEN** GBrain ingest uses the same normalized slug that wiki re-index would use for the same file
