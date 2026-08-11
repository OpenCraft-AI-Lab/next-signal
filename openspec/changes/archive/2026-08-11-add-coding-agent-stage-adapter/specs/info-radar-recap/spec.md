## RENAMED Requirements

- FROM: `### Requirement: Recap agent runs on `local_structured` with constrained output`
- TO: `### Requirement: Recap agent uses the selected production engine with validated output`

## MODIFIED Requirements

### Requirement: Recap agent uses the selected production engine with validated output

The recap SHALL invoke the registered agent configuration named `radar_recap`, declared in `configs/agents/radar_recap.yaml` with `extra: {db: false, shared_context: false}`, through the production stage adapter. The adapter SHALL use the job-selected engine and return a locally validated `RecapOutput{headline: str, themes: list[Theme]}` where `Theme{title: str, narrative: str, item_ids: list[int]}`. Static profile token limits SHALL apply to OMLX/DeepSeek routes; CLI routes SHALL remain bounded by their bridge configuration.

#### Scenario: agent configuration is reused

- **WHEN** the recap workflow needs its LLM step
- **THEN** it calls `run_stage("radar_recap", ..., output_schema=RecapOutput)`, preserving the existing prompt and language policy without constructing an inline hard-coded agent

#### Scenario: CLI recap is locally validated

- **WHEN** Codex or Claude is selected for recap generation
- **THEN** its response must validate as `RecapOutput` before citation validation or persistence begins
