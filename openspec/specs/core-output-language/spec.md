# core-output-language

One setting decides the language every agent writes its prose fields in, independent of the language of the source material.

## Purpose

Every LLM-writing prompt in the repo used to derive its output language from its input, which is the opposite of what the reader needs: a Chinese digest of an English article, without reading English. Measured on the shipped prompts, tier-2 `summary` came back English in 12/12 English-source cases while `impact` stayed Chinese in the very same responses, and `knowledge_frontmatter` — which had no language rule at all — flipped the same article between languages across runs.
## Requirements
### Requirement: Output language is one call-time setting

The system SHALL resolve the target output language through a per-agent **policy** rather than a single global source. An agent's policy is declared in its own config (`extra.output_language`) as one of `off`, `global`, `same_as_source`, or a literal `fixed:<lang>`. A bare `false` SHALL continue to mean `off`. When the key is absent, the policy SHALL default to `global`, matching the prior default-on behavior.

For the `global` policy, the system SHALL resolve the language from a runtime preference file (`~/.next-signal/language.json`, key `content_language`) if it exists, and SHALL fall back to a hardcoded constant (`"en"`) defined in code when it does not. The `SIGNAL_OUTPUT_LANG` environment variable SHALL NOT be read as part of this resolution — reading it was the prior mechanism and is retired. Recognized language values remain `zh` and `en`. An unrecognized value in the preference file SHALL raise `RuntimeError` naming the offending value, rather than falling back silently.

Resolution SHALL happen at call time, never at import time, so a preference-file change or a missing file cannot block startup and takes effect on the next agent build.

#### Scenario: global policy with a preference file present

- **WHEN** `~/.next-signal/language.json` contains `{"content_language": "zh"}` and an agent with policy `global` is built
- **THEN** the resolved language is `zh`

#### Scenario: global policy with no preference file

- **WHEN** `~/.next-signal/language.json` does not exist and an agent with policy `global` is built
- **THEN** the resolved language is the hardcoded default (`en`), and no error occurs

#### Scenario: a fresh `.env` has no effect on resolution

- **WHEN** `.env` is freshly copied from `.env.example`, with or without a language-related field, and no preference file exists
- **THEN** the resolved language is still the hardcoded default (`en`) — `.env` is not consulted

#### Scenario: unrecognized value in the preference file fails loud

- **WHEN** `~/.next-signal/language.json` contains `{"content_language": "fr"}` and an agent with policy `global` is built
- **THEN** a `RuntimeError` is raised naming `fr` and the recognized set, and no agent is returned

#### Scenario: preference file changes between calls

- **WHEN** `~/.next-signal/language.json` is rewritten after one agent has already been built
- **THEN** the next agent build observes the new value, because the file is read per call rather than cached at import

#### Scenario: `off` policy yields no rule

- **WHEN** an agent's policy is `off`
- **THEN** no language rule is appended and no substitution occurs, regardless of the preference file or the hardcoded default

### Requirement: The rule governs prose fields and exempts identifiers

The rule SHALL instruct the model to write **prose** fields in the target language regardless of the language of its input, and SHALL explicitly exempt identifier-like fields — tags, slugs, category paths — which remain lowercase English. It SHALL instruct the model to keep proper nouns (company, model, repository, paper and benchmark names) in their original form.

The rule SHALL be phrased unconditionally. It MUST NOT make the output language contingent on the language of the input, the goals, or the article body: the conditional phrasing is the measured cause of the drift this capability exists to prevent.

The rule SHALL NOT add per-field clauses naming individual output fields. A variant carrying such a clause was measured to hold language equally well while making output 35% longer and raising truncation failures against the `max_tokens` cap from 1/65 to 6/65.

#### Scenario: identifier fields survive a Chinese target

- **WHEN** the target language is `zh` and `knowledge_frontmatter` produces `tags`
- **THEN** the tags remain lowercase English and pass `_normalize_tags` without being dropped

#### Scenario: proper nouns are preserved

- **WHEN** the target language is `en` and the source article is Chinese
- **THEN** Chinese organisation and product names may be carried through, optionally glossed, rather than dropped or forcibly transliterated

### Requirement: Language is delivered in the prompt's own position

A prompt SHALL be able to declare the substitution token `{{OUTPUT_LANGUAGE}}` inside its own text; the system SHALL replace it with the resolved language name and SHALL NOT additionally append a rule block to that prompt. Only a prompt carrying no token receives an appended block.

A prompt that declares the token while its agent sets `extra: {output_language: false}` SHALL raise `RuntimeError` rather than ship the literal token to the model.

#### Scenario: token substituted in place

- **WHEN** a prompt declares the token and the target language is `en`
- **THEN** the token is replaced by "English", no `## Output language` block is appended, and the prompt's own final instruction is still the last line

#### Scenario: prompt without a token still gets the rule

- **WHEN** an agent's prompt declares no token and the agent is not opted out
- **THEN** the generated rule block is appended after the agent's instructions

#### Scenario: token in an opted-out prompt is rejected

- **WHEN** a prompt declares the token and its YAML sets `extra: {output_language: false}`
- **THEN** building the agent raises `RuntimeError` naming the conflict

### Requirement: Body-cleaning agents never receive the rule

`knowledge_artifact_editor` and `knowledge_github_cleaner` SHALL NOT resolve their output language from the `global` policy. Translating a cleaned body away from its source language would destroy the only copy of the source text held in the wiki. Instead, both agents SHALL use the `same_as_source` policy, so the rule they do receive is unconditional and explicit, resolved to the article's own detected language, rather than either the operator's global preference or an implicit, unstated default.

They are the **only** agents on this policy. The frontmatter agents (`knowledge_frontmatter`, `knowledge_github_summary`) SHALL use `global`: their `title` and `summary` are generated prose read in the dashboard's knowledge list and review cards, not preserved source text, so they belong with the operator's content-language preference. The dividing line is what the output *is* — an index entry written for the reader follows the setting; the archived body does not.

A wiki file MAY therefore hold frontmatter in one language over a body in another. This is intended, and matches how the radar reader already presents a translated title above a source-language article.

Two agents are `off`, both because they write no prose: `radar_dedup_judge`, whose `reason` is neither stored for display nor rendered anywhere, and `knowledge_classifier`, whose only output is a taxonomy path copied verbatim from its input. `off` SHALL NOT be treated as a free prompt saving — the rule block names `category paths` explicitly, and removing it from `knowledge_classifier` was measured to change filing on borderline items.

#### Scenario: cleaner targets the detected source language, not the global preference

- **WHEN** the global preference is `en` and an English-target run cleans a Chinese article
- **THEN** `knowledge_artifact_editor` resolves its policy to `zh` (the article's detected language) and returns the cleaned body still in Chinese

#### Scenario: frontmatter and body may differ in language

- **WHEN** the global preference is `en` and a Chinese article is ingested
- **THEN** the wiki file's body is Chinese (`same_as_source`) while its frontmatter `title` and `summary` are English (`global`), within the same file

#### Scenario: dedup judge is fully exempt

- **WHEN** any global preference or item content is present
- **THEN** `radar_dedup_judge` receives no language rule at all, and its `reason` field's language is unconstrained

### Requirement: Same-as-source policy requires a caller-supplied language

The `same_as_source` policy SHALL NOT resolve a language on its own — the workflow stage invoking the agent MUST supply the resolved language as a per-call override (e.g. `build_from_name(name, language=detected)`). If an agent whose policy is `same_as_source` is built without an override, the system SHALL raise `RuntimeError` rather than silently falling back to the global preference or the hardcoded default.

#### Scenario: override supplied

- **WHEN** an agent with policy `same_as_source` is built with `language="zh"`
- **THEN** the resolved language is `zh`, independent of the global preference file or `.env`

#### Scenario: override missing

- **WHEN** an agent with policy `same_as_source` is built with no `language` argument
- **THEN** a `RuntimeError` is raised naming the agent and the missing override, and no agent is returned

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

