## MODIFIED Requirements

### Requirement: Frontmatter prose fields follow the configured output language

The `title` and `summary` fields produced by `knowledge_frontmatter` (and by `knowledge_github_summary` for github sources) SHALL be written in the article's own detected source language (the `same_as_source` policy), not the operator's global output-language preference. A long-term knowledge archive exists to preserve the source as faithfully as possible; forcing frontmatter into an unrelated operator-wide preference — the prior behavior, which reused the same global setting info-radar uses — actively worked against that goal.

The detected language SHALL come from a single detection pass run once per ingested item — primarily against the item's title, falling back to the fetched raw body when no title exists — and SHALL be threaded as an explicit per-call override into both the frontmatter step and the body-cleaning step (see the requirement below), so both parts of one artifact agree. It SHALL NOT be re-run after cleaning.

The prompt SHALL state the target language unconditionally, using the resolved detected value — not a bare "match the source" instruction. An explicit, unconditional target reusing the resolved value was measured (in the prior global-setting form) to eliminate the same class of defect a conditional or implicit instruction produces; that same phrasing discipline carries over here, just fed a per-item detected value instead of a global one.

#### Scenario: English article ingested

- **WHEN** an English-language article is ingested, regardless of the operator's global output-language preference
- **THEN** `title` and `summary` are written in English, matching the detected source language

#### Scenario: Chinese article ingested under an English global preference

- **WHEN** a Chinese-language article is ingested while the dashboard's global content-language preference is set to English
- **THEN** `title` and `summary` are still written in Chinese — the global preference has no effect on this pipeline

#### Scenario: repeat ingests of one article agree

- **WHEN** the same article is ingested or re-indexed more than once
- **THEN** `title` and `summary` come back in the same (detected source) language every time

#### Scenario: github summary stops keying off repo content ambiguity

- **WHEN** a repository with English-only content is ingested
- **THEN** its `summary` is written in English, matching the detected language of that content

### Requirement: Body-cleaning agents are exempt from language conversion

`knowledge_artifact_editor` and `knowledge_github_cleaner` SHALL continue to emit the cleaned body in the source document's own language. Their policy SHALL be `same_as_source`, resolved from the same per-item detected language used by the frontmatter step — an explicit, unconditional target rather than the prior implicit behavior (no rule at all, relying on the model's default tendency to preserve input language during cleaning).

#### Scenario: cleaned body keeps its source language

- **WHEN** a Chinese article is ingested while the dashboard's global content-language preference is set to English
- **THEN** the wiki file's body remains Chinese (matching the detected source language) while its frontmatter `title` and `summary` are also Chinese — the global preference affects neither

#### Scenario: detected language is shared between cleaning and frontmatter

- **WHEN** one item is ingested
- **THEN** the language detected for it is computed once and used identically by both the body-cleaning step and the frontmatter step, so the two never disagree about what the source language is
