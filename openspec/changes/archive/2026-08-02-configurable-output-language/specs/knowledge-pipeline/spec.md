## ADDED Requirements

### Requirement: Frontmatter prose fields follow the configured output language

The `title` and `summary` fields produced by `knowledge_frontmatter` (and by
`knowledge_github_summary` for github sources) SHALL be written in the
configured output language, independent of the language of the article body.
The prompt SHALL state this unconditionally; it currently states nothing at all
about which language a field should be, leaving the choice to the model.

That silence is measurably unsafe: on English articles, 17.9% of titles and
7.7% of summaries came out pure English, and the same article flipped between
Chinese and English across repeat runs. A single manual check can pass while
the defect is present.

#### Scenario: English article under a Chinese target

- **WHEN** `SIGNAL_OUTPUT_LANG=zh` and an English article is ingested
- **THEN** `title` and `summary` are written in Chinese, with proper nouns kept in their original form

#### Scenario: repeat ingests of one article agree

- **WHEN** the same article is ingested or re-indexed more than once under an unchanged setting
- **THEN** `title` and `summary` come back in the same language every time

#### Scenario: github summary stops keying off repo content

- **WHEN** a repository with English-only content is ingested under `SIGNAL_OUTPUT_LANG=zh`
- **THEN** its `summary` is written in Chinese, rather than defaulting to English because the repo content is English

### Requirement: Tag language contract is unchanged and exempt

`tags` SHALL remain 3-5 lowercase English identifiers matching the existing
`_normalize_tags` contract, in every output language. The output-language rule
SHALL explicitly exempt them.

This is not a style preference: `_normalize_tags` silently drops any tag
containing CJK, so a rule that pushed tags into Chinese would not produce
Chinese tags — it would produce documents with no tags at all.

#### Scenario: Chinese target leaves tags English

- **WHEN** `SIGNAL_OUTPUT_LANG=zh` and an article is ingested
- **THEN** `tags` are lowercase English slugs and none are dropped by `_normalize_tags`

### Requirement: Body-cleaning agents are exempt from language conversion

`knowledge_artifact_editor` and `knowledge_github_cleaner` SHALL continue to
emit the cleaned body in the source document's own language, regardless of the
configured output language. Their YAML SHALL carry the opt-out explicitly rather
than relying on a default.

#### Scenario: cleaned body keeps its source language

- **WHEN** a Chinese article is ingested under `SIGNAL_OUTPUT_LANG=en`
- **THEN** the wiki file's body remains Chinese while its frontmatter `title` and `summary` are English
