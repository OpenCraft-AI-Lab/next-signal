## MODIFIED Requirements

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

### Requirement: Direct-agent path disables telemetry

When an agent is built outside the AgentOS context (CLI `run-agent`, tests), the loader SHALL pass `telemetry=False` to the agno `Agent` constructor.

#### Scenario: CLI run-agent does not phone home

- **WHEN** `next-signal run-agent <name> "<prompt>"` is invoked
- **THEN** the constructed agent has telemetry disabled
