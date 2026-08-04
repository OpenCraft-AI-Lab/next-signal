## MODIFIED Requirements

### Requirement: Body-cleaning agents never receive the rule

`knowledge_artifact_editor` and `knowledge_github_cleaner` SHALL NOT resolve their output language from the `global` policy. Translating a cleaned body away from its source language would destroy the only copy of the source text held in the wiki. Instead, both agents SHALL use the `same_as_source` policy, so the rule they do receive is unconditional and explicit, resolved to the article's own detected language, rather than either the operator's global preference or an implicit, unstated default.

They are the **only** agents on this policy. The frontmatter agents (`knowledge_frontmatter`, `knowledge_github_summary`) SHALL use `global`: their `title` and `summary` are generated prose read in the dashboard's knowledge list and review cards, not preserved source text, so they belong with the operator's content-language preference. The dividing line is what the output *is* — an index entry written for the reader follows the setting; the archived body does not.

A wiki file MAY therefore hold frontmatter in one language over a body in another. This is intended, and matches how the radar reader already presents a translated title above a source-language article.

`radar_dedup_judge` remains `off`: its `reason` is neither stored for display nor rendered anywhere, so no language resolution applies to it at all.

#### Scenario: cleaner targets the detected source language, not the global preference

- **WHEN** the global preference is `en` and an English-target run cleans a Chinese article
- **THEN** `knowledge_artifact_editor` resolves its policy to `zh` (the article's detected language) and returns the cleaned body still in Chinese

#### Scenario: frontmatter and body may differ in language

- **WHEN** the global preference is `en` and a Chinese article is ingested
- **THEN** the wiki file's body is Chinese (`same_as_source`) while its frontmatter `title` and `summary` are English (`global`), within the same file

#### Scenario: dedup judge is fully exempt

- **WHEN** any global preference or item content is present
- **THEN** `radar_dedup_judge` receives no language rule at all, and its `reason` field's language is unconstrained

### Requirement: Source language is detected deterministically, not via an LLM call

The system SHALL provide a `detect_language(text: str) -> str` function, behind a stable interface, for producing the override consumed by the `same_as_source` policy. The detection method SHALL be deterministic — the same input text SHALL always produce the same detected language across repeated invocations — and SHALL NOT use an LLM or any other sampling-based mechanism. The first implementation SHALL be a Unicode-script-ratio heuristic distinguishing `zh` from `en`, recognizing only the languages the rest of the system currently supports. The interface SHALL be structured so that replacing the heuristic with a more capable classifier (e.g. for additional languages) requires changing only the detection module, not any caller.

Detection SHALL run once per ingested item, primarily against the item's title — a short, reliably natural-language signal even for sources (such as READMEs) whose body is dominated by code or markup — falling back to the fetched raw body text when no title is available. It SHALL NOT be re-run after the body-cleaning step.

The detected value SHALL be threaded as a per-call override into the **body-cleaning step only**. The frontmatter step resolves `global` and SHALL NOT receive it.

#### Scenario: deterministic across repeated calls

- **WHEN** `detect_language` is called twice with byte-identical input
- **THEN** both calls return the same language, with no variance between runs

#### Scenario: Chinese-dominant text

- **WHEN** the input text's alphabetic characters are predominantly CJK-range codepoints
- **THEN** `detect_language` returns `zh`

#### Scenario: English-dominant text

- **WHEN** the input text's alphabetic characters are predominantly Latin-script
- **THEN** `detect_language` returns `en`

#### Scenario: detection never calls a model

- **WHEN** `detect_language` runs
- **THEN** no LLM API call, agent build, or network request occurs as part of detection

#### Scenario: title used as the primary signal

- **WHEN** an ingested item has a non-empty title
- **THEN** detection runs against the title, and the resulting language is threaded to the body-cleaning step without being re-run later

#### Scenario: fallback when no title is available

- **WHEN** an ingested item has no title
- **THEN** detection runs against the fetched raw body text instead

#### Scenario: frontmatter step ignores the detected value

- **WHEN** an item with detected language `zh` reaches the frontmatter step while the global preference is `en`
- **THEN** the frontmatter agent is built without a `language=` override and resolves `en` from the `global` policy
