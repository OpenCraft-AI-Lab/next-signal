## ADDED Requirements

### Requirement: A locked section's credential rejects a write

When a credential name belongs to a section that locks permanently once
committed (Radar Embedding's `RADAR_EMBEDDING_OPENAI_API_KEY` and
`EMBEDDING_API_KEY`; Knowledge Embedding's `OPENAI_API_KEY`,
`VOYAGE_API_KEY`, and `GOOGLE_GENERATIVE_AI_API_KEY`), and that section has
already been committed, a save or delete of that credential name SHALL be
rejected. This holds regardless of what withholds the request on the client,
so the store's own write path is the last line of defense rather than the
only one.

This requirement does not apply to a credential whose owning section has no
lock concept (for example `DEEPSEEK_API_KEY`, `FOLO_TOKEN`), which SHALL
remain writable at any time.

#### Scenario: a locked section's credential cannot be replaced

- **WHEN** `RADAR_EMBEDDING_OPENAI_API_KEY` is saved, Radar Embedding's OpenAI
  selection is then committed, and a save of `RADAR_EMBEDDING_OPENAI_API_KEY`
  is attempted afterward
- **THEN** the write is rejected and the previously stored value is unchanged

#### Scenario: a locked section's credential cannot be cleared

- **WHEN** Knowledge Embedding has been committed with a provider that
  required `VOYAGE_API_KEY`, and a delete of `VOYAGE_API_KEY` is attempted
  afterward
- **THEN** the delete is rejected and the credential remains present

#### Scenario: an unlocked section's credential is unaffected

- **WHEN** `DEEPSEEK_API_KEY` is saved or deleted at any time
- **THEN** the write succeeds, because the Engine section has no lock concept
