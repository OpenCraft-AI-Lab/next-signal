## MODIFIED Requirements

### Requirement: Recap agent runs on `local_structured` with constrained output

The recap SHALL invoke a registered agent named `radar_recap`, declared in `configs/agents/radar_recap.yaml` with `model_profile: local_structured` and `extra: {db: false, shared_context: false}`, its prompt in `prompts/agents/radar_recap.md`, invoked through `next_signal.agents.loader.build_from_name` and `next_signal.agents.structured.run_structured`. The agent SHALL return a structured output enforced by OMLX json_schema constrained decoding, shaped `RecapOutput{headline: str, themes: list[Theme]}` where `Theme{title: str, narrative: str, item_ids: list[int]}`. The `local_structured` `max_tokens` cap of 4096 MUST NOT be widened for this agent, nor overridden per-agent.

#### Scenario: agent is loaded from config, not constructed inline

- **WHEN** the recap workflow needs its LLM step
- **THEN** it calls `build_from_name("radar_recap")`, and no `Agent(...)` is constructed inline with hardcoded instructions or model id

#### Scenario: token cap is inherited unchanged

- **WHEN** `configs/agents/radar_recap.yaml` is loaded
- **THEN** it references `model_profile: local_structured` and declares no `max_tokens` override, inheriting the documented 4096 cap

### Requirement: Workflow is a manual entrypoint, not an AgentOS-exposed runnable

The recap SHALL be declared in `configs/workflows/info_radar_recap.yaml` with `expose.agent_os: false` and an `extra.run_now` pointing at the module entrypoint, following the existing info-radar workflow shells. Implementation SHALL live under `src/next_signal/workflows/info_radar_recap/`, with SQL confined to its `store.py`. Cadence is not part of this contract.

#### Scenario: workflow is reachable manually

- **WHEN** the operator runs `next-signal run-workflow info_radar_recap`
- **THEN** the config's `extra.run_now` entrypoint is invoked

#### Scenario: workflow is not bound by AgentOS

- **WHEN** AgentOS loads configured runnables
- **THEN** `info_radar_recap` is not exposed as an AgentOS workflow
