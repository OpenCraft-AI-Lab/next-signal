# core-stage-execution Specification

## Purpose
TBD - created by archiving change add-coding-agent-stage-adapter. Update Purpose after archive.
## Requirements
### Requirement: Production LLM stages use one provider-neutral adapter

Every shipped production LLM stage SHALL invoke `next_signal.agents.stage.run_stage` with an agent config name, stage input, optional output schema, and optional language override. The adapter SHALL reuse the agent YAML instructions, shared-context gate, and output-language policy. It SHALL route to exactly one of `omlx`, `deepseek`, `codex_cli`, or `claude_cli` without registering either CLI as an agno model, AgentOS agent, or tool.

#### Scenario: CLI engine runs an existing agent prompt

- **WHEN** a production stage invokes `run_stage("radar_tier2_impact", input, output_schema=Tier2Analysis)` in a Claude CLI job
- **THEN** the adapter composes `radar_tier2_impact`'s existing instructions and language rule, invokes the bounded Claude bridge once per attempt under the isolated stage profile, and returns a validated `Tier2Analysis`

#### Scenario: AgentOS construction remains an agno path

- **WHEN** the runnable loader registers configured agents with AgentOS
- **THEN** it continues to use `build_from_name` and no Codex/Claude stage adapter is registered as an agno model or runnable

### Requirement: Live engine preferences are strict runtime state

The adapter SHALL read `engine.json` at the start of each top-level production job and validate the engine enum, fallback enum, OMLX endpoint/model/parallelism, DeepSeek model/reasoning, and unknown keys. Absence SHALL resolve the same baseline as the Dashboard from `configs/models.yaml` and `OMLX_BASE_URL`; malformed state SHALL fail the job loudly. CLI model/effort/speed SHALL continue to come from the separately validated `coding-agents.json`.

#### Scenario: Dashboard selection applies to the next job

- **WHEN** `engine.json` selects `codex_cli` before an info-radar job starts
- **THEN** every LLM stage in that job invokes Codex with the explicit settings in `coding-agents.json`

#### Scenario: Settings change does not split an active job

- **WHEN** `engine.json` is changed after a production job has started
- **THEN** the active job keeps its original in-memory preferences and the next job reads the new selection

#### Scenario: Invalid state fails loud

- **WHEN** `engine.json` contains an unknown engine or unknown field
- **THEN** the job raises a validation error before invoking an LLM

### Requirement: One engine is pinned for a whole production job

A top-level production job SHALL run inside a stage-job context shared by all of its LLM stages and worker threads. A configured fallback MAY replace an unreachable primary only before the first successful LLM response. Once a provider returns any successful response, the job SHALL pin that engine and SHALL NOT switch providers for later invocation or schema errors.

#### Scenario: Primary fails before first response

- **WHEN** the first stage cannot invoke the primary and a different fallback is configured
- **THEN** the adapter retries that stage on the fallback and, on success, uses the fallback for every remaining stage

#### Scenario: Later provider failure does not mix engines

- **WHEN** Tier 1 succeeds on the primary and Tier 2 later fails to invoke it
- **THEN** Tier 2 fails under the workflow's existing isolation policy and the adapter does not call the fallback

#### Scenario: Schema repair stays on the selected engine

- **WHEN** a provider returns a successful response that fails schema validation
- **THEN** the adapter locks that provider and sends the validation-feedback repair to the same provider

#### Scenario: Direct AgentOS workflow preserves affinity

- **WHEN** AgentOS invokes the exposed knowledge-ingest workflow through its sync, async, or streaming entrypoint
- **THEN** the workflow binds one stage-job state for the complete execution and every cleaner, frontmatter, and classifier call uses its pinned engine

### Requirement: A job's model settings are frozen when it starts

A stage job SHALL read every runtime preference file it needs — engine selection and coding-agent CLI defaults alike — once, when the job opens, and SHALL use those values for every stage and every worker thread within it. No stage SHALL re-read a preference file mid-job, and the job's recorded provenance SHALL report the frozen values rather than the file's current contents.

Pinning the engine without pinning the model it runs is only half a guarantee. A radar job runs for tens of minutes over a batch whose scores are ranked against each other, and the settings page is editable throughout, so a per-stage re-read scores the front and back halves of one batch with different models — silently, and in a way the provenance record would misattribute.

#### Scenario: A settings edit mid-job does not reach that job

- **WHEN** the operator changes the Codex model on the settings page while a stage job is running
- **THEN** the job's remaining stages still invoke the model that was configured when it started, and the next job picks up the new one

#### Scenario: Provenance describes the job, not the file

- **WHEN** an evaluation harness records engine provenance after a job whose preference file changed mid-run
- **THEN** the recorded CLI model and effort are the ones the job actually used

### Requirement: CLI stages are invocable from asynchronous callers

A CLI stage SHALL complete whether or not an event loop is already running on the calling thread. AgentOS reaches production stages through the workflow's asynchronous entrypoint, and the workflow engine executes a synchronous step inline on the loop thread, so an invocation that assumes no running loop fails there.

That failure SHALL NOT be indistinguishable from an unreachable provider. Raised inside the invocation path, it is caught as a provider failure and silently answered with the configured fallback, which reads as a missing CLI rather than a wrong call and leaves the selected engine permanently unused on that surface.

#### Scenario: A CLI stage runs under a live event loop

- **WHEN** AgentOS runs the exposed knowledge-ingest workflow asynchronously with a CLI engine selected
- **THEN** the CLI stage executes on that engine and returns its result, rather than failing over to the fallback engine

### Requirement: Structured output is provider-neutral and locally authoritative

For a structured stage the adapter SHALL derive JSON Schema from the supplied Pydantic model, deliver it through the selected provider's supported mechanism, and always validate locally. Parsing SHALL attempt strict JSON extraction/validation, then JSON5 tolerance, then at most one repair turn containing the validation error. A still-invalid response SHALL raise `RuntimeError` and SHALL NOT be persisted as a successful stage result.

#### Scenario: Claude receives provider-native schema

- **WHEN** a structured stage runs on Claude Code
- **THEN** the bridge argv contains `--json-schema` with the Pydantic-derived schema and the returned result is also validated locally

#### Scenario: Codex receives schema in its prompt

- **WHEN** a structured stage runs on Codex CLI
- **THEN** the composed prompt contains the Pydantic-derived schema, no unsupported schema flag is emitted, and local validation enforces it

#### Scenario: Plain-text stage remains plain text

- **WHEN** a knowledge cleaner invokes `run_stage` without an output schema
- **THEN** the adapter returns the provider's non-empty text without forcing a JSON wrapper

### Requirement: Production CLI stages stay bounded and non-mutating

Codex and Claude production stages SHALL use the existing coding-agent bridge's dedicated `stage` profile, fixed executable mapping, safe environment, timeout, output bound, JSONL parser, and one-shot session behavior. Each attempt SHALL run in a fresh empty temporary directory that is the runner's only allowed root. Codex SHALL ignore user/repository instructions and disable tool-bearing features. Claude SHALL use safe mode, disable slash commands, and expose an empty built-in tool set. Prompt instructions SHALL remain a defense-in-depth reminder rather than the security boundary. CLI concurrency SHALL be bounded by configured provider limits.

#### Scenario: CLI stage cannot mutate the repository

- **WHEN** a production workflow selects either CLI engine
- **THEN** Codex receives the read-only sandbox plus disabled tool features, Claude receives safe mode plus `--tools ""`, neither process can see repository files from its empty workspace, and the browser/user cannot supply an alternate command or working directory

#### Scenario: Operator repository commands retain their profiles

- **WHEN** an operator directly invokes `next-signal coding-agent run` with review or edit
- **THEN** the configured repository review/edit capabilities remain available and are not replaced by the production stage profile

#### Scenario: Concurrent stage calls respect provider limit

- **WHEN** more CLI stage calls run concurrently than `configs/models.yaml` permits for that CLI engine
- **THEN** excess calls wait on the provider semaphore instead of spawning unbounded CLI processes

### Requirement: Non-LLM workflow steps are not rerouted

Engine selection SHALL govern text-generating/judging LLM stages only. Fetchers, deterministic validation, database persistence, GBrain operations, the OMLX embedding model, and pgvector ANN search SHALL retain their current implementations and configuration.

#### Scenario: CLI radar job still uses compatible embedding

- **WHEN** Tier 2 runs through Codex or Claude and reaches dedup
- **THEN** its summary is embedded through the configured `embedders.local` OMLX endpoint before the selected CLI performs only the candidate judge stage

### Requirement: Evaluation harnesses preserve and record engine identity

Every shipped multi-stage evaluation harness SHALL open one stage-job context
for the complete run, invoke production LLM stages through `run_stage`, and
record the actual selected engine plus its frozen model/effort/speed settings.
Prompt digests used for comparisons SHALL include that provenance.

#### Scenario: Evaluation primary falls back

- **WHEN** an evaluation's primary engine fails before its first successful response and the fallback succeeds
- **THEN** every later stage uses that fallback and the result metadata records the fallback's actual engine and explicit settings

