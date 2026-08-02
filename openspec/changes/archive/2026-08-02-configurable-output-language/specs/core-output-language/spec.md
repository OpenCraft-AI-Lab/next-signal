## ADDED Requirements

### Requirement: Output language is one call-time setting

The system SHALL read the target output language from the `SIGNAL_OUTPUT_LANG`
environment variable at **call time**, never at import time, so a missing value
cannot block startup. Recognized values are `zh` and `en`. When the variable is
unset or empty, a prompt carrying the substitution token SHALL still resolve to
the default language (Simplified Chinese, the language the prompts were written
against) so it reads as a complete sentence, and no rule SHALL be appended to
prompts that carry no token. When the variable holds any other value, the system SHALL
raise `RuntimeError` naming the offending value and the recognized set, rather
than falling back to a default.

The variable name SHALL NOT use the `PACA_` prefix, per the project's naming
convention for new environment variables.

#### Scenario: recognized language selected

- **WHEN** `SIGNAL_OUTPUT_LANG=zh` and an agent is built
- **THEN** the resolved language is `zh` and the output-language rule is generated for Chinese

#### Scenario: variable unset

- **WHEN** `SIGNAL_OUTPUT_LANG` is unset or empty and an agent whose prompt has no token is built
- **THEN** no output-language rule is appended and the agent's own prompt is unmodified

#### Scenario: variable unset with a token-carrying prompt

- **WHEN** `SIGNAL_OUTPUT_LANG` is unset and the prompt declares the substitution token
- **THEN** the token resolves to the default language so the sentence is complete, and no literal token reaches the model

#### Scenario: unrecognized value fails loud

- **WHEN** `SIGNAL_OUTPUT_LANG=fr` and an agent is built
- **THEN** a `RuntimeError` is raised naming `fr` and the recognized values, and no agent is returned

#### Scenario: value changes between calls

- **WHEN** `SIGNAL_OUTPUT_LANG` is changed after one agent has already been built
- **THEN** the next agent build observes the new value, because the variable is read per call rather than cached at import

### Requirement: The rule governs prose fields and exempts identifiers

The generated rule SHALL instruct the model to write **prose** fields in the
target language regardless of the language of its input, and SHALL explicitly
exempt identifier-like fields — tags, slugs, category paths — which remain
lowercase English. The rule SHALL instruct the model to keep proper nouns
(company, model, repository, paper and benchmark names) in their original form.

The rule SHALL be phrased unconditionally. It MUST NOT make the output language
contingent on the language of the input, the goals, or the article body, because
a conditional phrasing is the measured cause of the drift this change fixes.

The rule SHALL NOT add per-field clauses naming individual output fields.
Field-level clauses were measured to hold language equally well while making
output 35% longer and raising truncation failures against the `max_tokens` cap
from 1/65 to 6/65.

#### Scenario: identifier fields survive a Chinese target

- **WHEN** the target language is `zh` and `knowledge_frontmatter` produces `tags`
- **THEN** the tags remain lowercase English and pass `_normalize_tags` without being dropped

#### Scenario: proper nouns are preserved

- **WHEN** the target language is `en` and the source article is Chinese
- **THEN** Chinese organisation and product names may be carried through, optionally glossed, rather than dropped or forcibly transliterated

### Requirement: Body-cleaning agents never receive the rule

Agents whose output is the article body itself — `knowledge_artifact_editor` and
`knowledge_github_cleaner` — SHALL be permanently exempt from the
output-language rule. Translating a cleaned body would destroy the only copy of
the source text held in the wiki.

#### Scenario: cleaner keeps the source language

- **WHEN** `SIGNAL_OUTPUT_LANG=en` and an English-target run cleans a Chinese article
- **THEN** `knowledge_artifact_editor` returns the cleaned body still in Chinese

### Requirement: Language is delivered in the prompt's own position

A prompt SHALL be able to declare the substitution token `{{OUTPUT_LANGUAGE}}`
inside its own text; the system SHALL replace it with the resolved language name
and SHALL NOT additionally append a rule block to that prompt. Only a prompt
carrying no token receives an appended block.

In-place substitution is required because appending a rule after a prompt
displaces that prompt's own closing instructions. Measured on the 55-item
holdout set, appending raised `impact` output ~31% and truncation failures from
2/165 to 7/165 against the `max_tokens` cap, while the in-prompt position is the
one the language fix was originally measured in.

A prompt that declares the token while its agent sets
`extra: {output_language: false}` SHALL raise `RuntimeError` rather than ship the
literal token to the model.

#### Scenario: token substituted in place

- **WHEN** a prompt declares the token and the target language is `en`
- **THEN** the token is replaced by "English", no `## Output language` block is appended, and the prompt's own final instruction is still the last line

#### Scenario: prompt without a token still gets the rule

- **WHEN** an agent's prompt declares no token and the agent is not opted out
- **THEN** the generated rule block is appended after the agent's instructions

#### Scenario: token in an opted-out prompt is rejected

- **WHEN** a prompt declares the token and its YAML sets `extra: {output_language: false}`
- **THEN** building the agent raises `RuntimeError` naming the conflict
