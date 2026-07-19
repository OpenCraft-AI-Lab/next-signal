# core-agents

YAML-driven agent loader. Python defines the *shape*; YAML defines model profile, instructions, tools, and behavior knobs.

## Purpose

Adding or tuning an agent must not require Python edits. Each agent is described by `configs/agents/<name>.yaml` plus an optional `prompts/agents/<name>.md`.

## Requirements

### Requirement: Agents are defined in YAML

The loader SHALL build each agent from `configs/agents/<name>.yaml`, where the file stem matches the YAML `name:` field (snake_case).

#### Scenario: agent built from name

- **WHEN** `paca.agents.loader.build_from_name("knowledge_classifier")` is called
- **THEN** the loader reads `configs/agents/knowledge_classifier.yaml`, resolves the model profile, attaches the listed tools, and returns an agno `Agent`

#### Scenario: agent instructions use owner path

- **WHEN** `configs/agents/knowledge_manager.yaml` sets `instructions_file: agents/knowledge_manager.md`
- **THEN** the loader reads `prompts/agents/knowledge_manager.md`

#### Scenario: hard-coded model is rejected

- **WHEN** an agent module attempts to instantiate a provider class directly (e.g. `Claude(...)`)
- **THEN** that is treated as a bug — model identity must come from `configs/models.yaml` profiles via the model factory

### Requirement: Shared context prepended to instructions

The loader SHALL prepend the concatenation of `prompts/_shared/*.md` (alphabetical, files starting with `_` skipped) to each agent's instructions.

#### Scenario: shared house rules apply by default

- **WHEN** an agent is built without `extra: {shared_context: false}`
- **THEN** the rendered instructions begin with the shared block followed by the agent-specific instructions

#### Scenario: agent opts out of shared context

- **WHEN** an agent's YAML sets `extra: {shared_context: false}`
- **THEN** only the agent-specific instructions are used

### Requirement: Direct-agent path disables telemetry

When an agent is built outside the AgentOS context (CLI `run-agent`, tests), the loader SHALL pass `telemetry=False` to the agno `Agent` constructor.

#### Scenario: CLI run-agent does not phone home

- **WHEN** `paca run-agent <name> "<prompt>"` is invoked
- **THEN** the constructed agent has telemetry disabled
