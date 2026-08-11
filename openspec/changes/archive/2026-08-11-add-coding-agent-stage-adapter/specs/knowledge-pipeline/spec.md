## MODIFIED Requirements

### Requirement: Artifact editing is split into a clean pass and a frontmatter pass

The pipeline SHALL transform a fetched source packet into cleaned markdown and frontmatter draft fields (`title`, `summary`, `tags`, `freshness`) via two separate production stage-adapter calls rather than one combined call: `clean_body` (the `clean` step) runs the `knowledge_artifact_editor` configuration (or `knowledge_github_cleaner` for GitHub sources) and returns plain cleaned markdown text with no schema; `write_frontmatter` (the `enrich` step) separately runs `knowledge_frontmatter` (or `knowledge_github_summary` for GitHub sources) under the `FrontmatterDraft` Pydantic schema. Both calls SHALL use the same engine pinned for the ingest job. This split keeps each output small and focused while remaining independent of provider.

#### Scenario: orchestrator avoids full-body editing

- **WHEN** a fetched markdown packet is ready for content processing
- **THEN** the orchestrator passes the packet to `clean_body` and `write_frontmatter` in turn and does not generate cleaned markdown or frontmatter itself

#### Scenario: clean pass returns plain markdown, not structured output

- **WHEN** `clean_body` runs through any selected engine
- **THEN** it returns plain cleaned markdown text with no forced JSON wrapper, while `write_frontmatter` is validated as `FrontmatterDraft`

### Requirement: LLM artifact edit and frontmatter enrichment fail loud

`clean_body` and `write_frontmatter` SHALL together populate cleaned markdown plus `summary`, `tags`, `freshness` (`permanent` / `stable` / `evolving` / `ephemeral`), and source metadata across their two adapter calls. If either provider invocation or `write_frontmatter` structured-output validation fails, the workflow SHALL fail loud rather than writing deterministic fallback content.

#### Scenario: transcript summary is rejected

- **WHEN** the source contains a transcript and the edited markdown removes the transcript section or compresses the body below the configured retention threshold
- **THEN** validation fails and the artifact is not written

#### Scenario: invalid frontmatter is rejected

- **WHEN** the selected engine returns empty summary text, invalid freshness, or tags that do not match the required lowercase English tag format
- **THEN** validation fails and the artifact is not written

#### Scenario: editor call unavailable

- **WHEN** the selected engine cannot complete the required edit
- **THEN** the save operation raises a loud failure and no clean wiki artifact is written

#### Scenario: clean-step retry is a blind step re-run

- **WHEN** the `clean` step (`max_retries=1`) fails validation such as the retention guard
- **THEN** the workflow step re-runs `clean_body` from the same input on the job's pinned engine rather than sending validation feedback; a second failure raises loud

#### Scenario: frontmatter-step retry uses schema-validation feedback

- **WHEN** `write_frontmatter` produces output that fails `FrontmatterDraft` validation
- **THEN** the stage adapter re-prompts the same selected engine with the exact validation error once, and a still-invalid result raises `RuntimeError`

#### Scenario: related links empty when no matches

- **WHEN** the post-ingest hybrid `gbrain_query` against the article's title and summary returns no other-page results
- **THEN** the article is written without a `## Related` marker block; refresh cycles re-add one if the brain later finds neighbors

## ADDED Requirements

### Requirement: Classification uses the ingest job's selected engine

When no category override is supplied, `knowledge_classifier` SHALL run through the same stage-job context and pinned engine as the clean and frontmatter passes. Its existing `temp-inbox` fallback on classification failure SHALL remain unchanged.

#### Scenario: one CLI performs every knowledge LLM pass

- **WHEN** a knowledge ingest starts with Codex selected and no category override
- **THEN** cleaner, frontmatter, and classifier LLM calls all use Codex while deterministic fetch, validation, persistence, and GBrain calls retain their existing implementations
