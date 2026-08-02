## MODIFIED Requirements

### Requirement: Shared context prepended to instructions

The loader SHALL **append** the concatenation of `prompts/_shared/*.md`
(alphabetical, files starting with `_` skipped) to each agent's instructions.
This reverses the previous prepend ordering so that the agent's own role and
field contract are read first and the shared block trails as a qualifier.

The shared block SHALL NOT assert precedence over per-agent instructions, and
SHALL NOT contain any rule that ties output language to the language of the
input. Language is governed solely by the output-language rule.

#### Scenario: shared house rules apply by default

- **WHEN** an agent is built without `extra: {shared_context: false}`
- **THEN** the rendered instructions begin with the agent-specific instructions followed by the shared block

#### Scenario: agent opts out of shared context

- **WHEN** an agent's YAML sets `extra: {shared_context: false}`
- **THEN** the shared block is omitted entirely

#### Scenario: shared block carries no language rule

- **WHEN** the shared context files are loaded
- **THEN** they contain no instruction to match the language of the user's message, the goals, or the article body

## ADDED Requirements

### Requirement: Output-language delivery is on its own gate

The loader SHALL deliver the output language two ways. When the agent's own
instructions declare `{{OUTPUT_LANGUAGE}}`, the loader SHALL substitute the
resolved language name in place and append no rule block. Otherwise it SHALL
append the generated rule **last**, after both the agent-specific instructions
and any shared-context block. Either way, inclusion SHALL be controlled by
`extra: {output_language: false}`, a gate independent of
`extra: {shared_context: false}`.

The two gates MUST remain independent: the production agents that opt out of
shared context still need the language rule, and forcing them to accept the
house-rules block to get it would inject conciseness and citation directives
that conflict with their field contracts.

When `SIGNAL_OUTPUT_LANG` is unset, no rule is appended regardless of the gate.

#### Scenario: agent opted out of shared context still gets the language rule

- **WHEN** an agent whose prompt has no token sets `extra: {shared_context: false}` and does not set `output_language: false`, and `SIGNAL_OUTPUT_LANG=zh`
- **THEN** the rendered instructions contain the agent's own prompt plus the appended Chinese output-language rule, and no house-rules block

#### Scenario: agent opts out of the language rule only

- **WHEN** an agent sets `extra: {output_language: false}` and `SIGNAL_OUTPUT_LANG=zh`
- **THEN** no language rule is appended, while any shared-context block it is entitled to is still appended

#### Scenario: appended rule is last in the composed prompt

- **WHEN** an agent whose prompt has no token is entitled to both blocks and `SIGNAL_OUTPUT_LANG` is set
- **THEN** the composition order is agent instructions, then shared context, then the output-language rule

#### Scenario: a token-carrying prompt keeps its own closing instruction last

- **WHEN** an agent whose prompt declares the token is built with `SIGNAL_OUTPUT_LANG` set
- **THEN** the language name is substituted inside the prompt, no rule block is appended, and the prompt's own final line remains final
