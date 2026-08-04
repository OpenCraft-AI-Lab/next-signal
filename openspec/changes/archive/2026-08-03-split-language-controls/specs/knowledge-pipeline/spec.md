## MODIFIED Requirements

### Requirement: Frontmatter prose fields follow the configured output language

The `title` and `summary` fields produced by `knowledge_frontmatter` (and by `knowledge_github_summary` for github sources) SHALL be written in the operator's configured content language (the `global` policy), not the article's detected source language. These fields are the artifact's index entry — they are what the dashboard's knowledge list and review cards display — so they are generated prose written for the reader, and belong with the setting that governs generated prose. The archive is preserved by the body, which keeps its source language (see the body-cleaning requirement below); forcing the *index* into the source's language instead made a reader's own knowledge index unreadable to them.

Both agents' prompts already carry the `{{OUTPUT_LANGUAGE}}` substitution token and state the target unconditionally ("regardless of the language of the article body"). That measured wording SHALL NOT change as part of this policy move — only the source the token resolves from changes.

The frontmatter step SHALL NOT receive a per-call `language=` override. Its agents resolve `global` on their own, at call time, so a change to the preference takes effect on the next ingest without a restart.

#### Scenario: English article ingested

- **WHEN** an English-language article is ingested while the content-language setting is `zh`
- **THEN** `title` and `summary` are written in Chinese

#### Scenario: Chinese article ingested under an English global preference

- **WHEN** a Chinese-language article is ingested while the content-language setting is `en`
- **THEN** `title` and `summary` are written in English, while the body stays Chinese

#### Scenario: repeat ingests of one article agree

- **WHEN** the same article is ingested more than once without the content-language setting changing
- **THEN** `title` and `summary` come back in the same language every time

#### Scenario: github summary stops keying off repo content ambiguity

- **WHEN** a repository is ingested while the content-language setting is `zh`
- **THEN** its `summary` is written in Chinese regardless of the repo's own content language, while `title` stays the `owner/repo` identifier

#### Scenario: changing the setting never rewrites existing documents

- **WHEN** the content-language setting is changed and the wiki is re-indexed
- **THEN** existing wiki files keep the frontmatter they were written with and no file is renamed — `reindex_wiki` re-embeds markdown into GBrain and SHALL NOT re-run the frontmatter step, so a document's `title` changes only when its source is ingested again

### Requirement: Tag language contract is unchanged and exempt

`tags` SHALL remain 3-5 lowercase English identifiers matching the existing
`_normalize_tags` contract, in every output language. The output-language rule
SHALL explicitly exempt them.

This is not a style preference: `_normalize_tags` silently drops any tag
containing CJK, so a rule that pushed tags into Chinese would not produce
Chinese tags — it would produce documents with no tags at all.

#### Scenario: Chinese target leaves tags English

- **WHEN** the frontmatter agent's resolved language is `zh` (the content-language setting under the `global` policy) and an article is ingested
- **THEN** `tags` are lowercase English slugs and none are dropped by `_normalize_tags`

## REMOVED Requirements

### Requirement: Body-cleaning agents are exempt from language conversion

**Reason**: Its `detected language is shared between cleaning and frontmatter`
scenario asserts the exact link this change severs — detection now feeds the
body cleaners alone. A MODIFIED block cannot drop a scenario, and keeping that
header over an inverted body would leave the spec contradicting its own
scenario title.

**Migration**: Replaced below by "Body cleaning targets the detected source
language", which carries the same normative text plus the fact that the cleaners
are now detection's only consumers. Its emphasis moves from "exempt from
conversion" (true when nothing else converted either) to "targets the source,
not the setting", which is the distinction that now matters.

## ADDED Requirements

### Requirement: Body cleaning targets the detected source language

`knowledge_artifact_editor` and `knowledge_github_cleaner` SHALL continue to emit the cleaned body in the source document's own language. Their policy SHALL be `same_as_source`, resolved from the per-item detected language, which the ingest workflow SHALL pass as an explicit `language=` override — an explicit, unconditional target rather than the prior implicit behavior (no rule at all, relying on the model's default tendency to preserve input language during cleaning).

They are the only consumers of the detected language. Detection itself is unchanged: computed once per item in `fetch()`, primarily from the title, and carried on `KnowledgeArtifact.detected_language`.

#### Scenario: cleaned body keeps its source language

- **WHEN** a Chinese article is ingested while the content-language setting is `en`
- **THEN** the wiki file's body remains Chinese, matching the detected source language, while its frontmatter `title` and `summary` are English

#### Scenario: detection feeds body cleaning only

- **WHEN** one item is ingested
- **THEN** its language is detected once and passed as `language=` to the body-cleaning agent only; the frontmatter agent is built with no override
