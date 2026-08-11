# core-agents

YAML-driven agent loader. Python defines the *shape*; YAML defines model profile, instructions, tools, and behavior knobs.

## Purpose

Adding or tuning an agent must not require Python edits. Each agent is described by `configs/agents/<name>.yaml` plus an optional `prompts/agents/<name>.md`.
## Requirements
### Requirement: Agents are defined in YAML

The loader SHALL build each agent from `configs/agents/<name>.yaml`, where the file stem matches the YAML `name:` field (snake_case).

#### Scenario: agent built from name

- **WHEN** `next_signal.agents.loader.build_from_name("knowledge_classifier")` is called
- **THEN** the loader reads `configs/agents/knowledge_classifier.yaml`, resolves the model profile, attaches the listed tools, and returns an agno `Agent`

#### Scenario: agent instructions use owner path

- **WHEN** `configs/agents/knowledge_classifier.yaml` sets `instructions_file: agents/knowledge_classifier.md`
- **THEN** the loader reads `prompts/agents/knowledge_classifier.md`

#### Scenario: hard-coded model is rejected

- **WHEN** an agent module attempts to instantiate a provider class directly (e.g. `Claude(...)`)
- **THEN** that is treated as a bug — model identity must come from `configs/models.yaml` profiles via the model factory

### Requirement: Shared context appended to instructions

The loader SHALL **append** the concatenation of `prompts/_shared/*.md` (alphabetical, files starting with `_` skipped) to each agent's instructions, after the agent's own text.

The `# Agent role` heading SHALL appear only when the shared block is actually present — it exists solely to separate the two, and adding it unconditionally silently rewrites the prompt of every agent that opts out.

The shared block SHALL NOT assert precedence over per-agent instructions, and SHALL NOT contain any rule that ties output language to the language of the input. Language is governed solely by the output-language rule.

#### Scenario: shared house rules apply by default

- **WHEN** an agent is built without `extra: {shared_context: false}`
- **THEN** the rendered instructions begin with the agent-specific instructions under a `# Agent role` heading, followed by the shared block

#### Scenario: agent opts out of shared context

- **WHEN** an agent's YAML sets `extra: {shared_context: false}`
- **THEN** the shared block is omitted and the agent-specific instructions ship bare, with no `# Agent role` heading

#### Scenario: shared block carries no language rule

- **WHEN** the shared context files are loaded
- **THEN** they contain no instruction to match the language of the user's message, the goals, or the article body

### Requirement: Output-language delivery is on its own gate

The loader SHALL deliver the output language two ways. When the agent's own instructions declare `{{OUTPUT_LANGUAGE}}`, the loader SHALL substitute the resolved language name in place and append no rule block. Otherwise it SHALL append the generated rule last, after both the agent-specific instructions and any shared-context block. Either way, inclusion SHALL be controlled by `extra: {output_language: false}`, a gate independent of `extra: {shared_context: false}`.

The two gates MUST remain independent: every production agent opts out of shared context yet still needs the language rule, and forcing them to accept the house-rules block to get it would inject conciseness and citation directives that conflict with their field contracts.

Appending the rule SHALL NOT introduce the `# Agent role` heading.

#### Scenario: agent opted out of shared context still gets the language rule

- **WHEN** an agent whose prompt has no token sets `extra: {shared_context: false}` and does not set `output_language: false`, and `SIGNAL_OUTPUT_LANG=zh`
- **THEN** the rendered instructions contain the agent's own prompt plus the appended Chinese output-language rule, with no house-rules block and no `# Agent role` heading

#### Scenario: agent opts out of the language rule only

- **WHEN** an agent sets `extra: {output_language: false}` and `SIGNAL_OUTPUT_LANG=zh`
- **THEN** no language rule is delivered, while any shared-context block it is entitled to is still appended

#### Scenario: a token-carrying prompt keeps its own closing instruction last

- **WHEN** an agent whose prompt declares the token is built with `SIGNAL_OUTPUT_LANG` set
- **THEN** the language name is substituted inside the prompt, no rule block is appended, and the prompt's own final line remains final

### Requirement: Direct-agent path disables telemetry

When an agent is built outside the AgentOS context (CLI `run-agent`, tests), the loader SHALL pass `telemetry=False` to the agno `Agent` constructor.

#### Scenario: CLI run-agent does not phone home

- **WHEN** `next-signal run-agent <name> "<prompt>"` is invoked
- **THEN** the constructed agent has telemetry disabled

