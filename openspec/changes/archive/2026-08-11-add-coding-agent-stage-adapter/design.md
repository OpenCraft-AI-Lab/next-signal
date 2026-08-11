## Context

Production LLM calls currently follow `build_from_name(...)` plus either `agent.run(...)` or `run_structured(...)`. That path always constructs an agno `Agent` from the YAML `model_profile`. The Dashboard's `engine.json` selection is deliberately not read, while the coding-agent bridge exposes Codex and Claude only as bounded one-shot repository workers.

The measured smoke test shows both CLIs can execute the current radar prompts and return valid Tier 1, Tier 2, and dedup schemas. It also shows why an adapter is required: the CLI is an agent process with its own event protocol, not an agno model client. Current production agents have no tools, so presenting their composed instructions plus input to one external CLI turn preserves their stage contract without nesting next-signal tools inside the provider.

## Goals / Non-Goals

**Goals:**

- Make the Dashboard's selected engine govern every current production LLM stage.
- Preserve agent YAML, composed instructions, output-language policy, Pydantic schemas, repair behavior, and workflow persistence contracts.
- Pin one engine per top-level job and provide bounded, pre-first-success fallback.
- Use provider-native schema delivery when available and validate every provider output locally.
- Apply live OMLX/DeepSeek settings and explicit Codex/Claude settings without restarting services.

**Non-Goals:**

- Register Codex or Claude as agno `Model` implementations, AgentOS agents, tools, or resumable sessions.
- Move deterministic fetching, embeddings, ANN, database writes, or GBrain operations to a coding-agent CLI.
- Give a production stage repository visibility, mutation, shell, browser, MCP,
  plugin, or delegated-agent permissions. Repository review/edit commands remain
  separate operator-invoked surfaces.
- Persist raw prompts, model output, provider events, or job-affinity state.

## Decisions

### 1. Add `agents.stage.run_stage`, not a fake agno model

`run_stage(agent_name, input, output_schema=None, language=None)` loads the existing `AgentConfig` and composes instructions through the same loader helper. For OMLX/DeepSeek it constructs an ordinary agno agent with a runtime-selected model. For Codex/Claude it sends one combined instruction/input prompt through `run_coding_agent` under a dedicated no-tools `stage` profile in a fresh empty temporary directory. Codex ignores user/repository instructions and disables tool-bearing features; Claude uses safe mode and an empty built-in tool set.

This keeps workflow call sites provider-neutral while preserving the bridge boundary. Implementing an agno `Model` wrapper around an autonomous CLI was rejected because agno would treat a second agent loop as a token-completion endpoint and could recursively expose tools or history semantics the CLI owns itself.

### 2. Read and validate `engine.json` in Python at job start

A strict Python schema mirrors the Dashboard's four engines and their OMLX/DeepSeek fields. Absence resolves from `configs/models.yaml` and `OMLX_BASE_URL`, matching the Dashboard baseline; malformed or unknown values fail loud in production. `coding-agents.json` remains the sole source for CLI model/effort/speed.

Each top-level production workflow opens a `stage_job()` context. The resolved preferences are held in memory for that job, so changing settings affects the next job rather than switching a job mid-flight.

The AgentOS-exposed knowledge workflow owns this boundary in its `Workflow`
subclass, including sync, async, and streaming execution. Direct AgentOS calls
therefore have the same affinity as CLI/Dashboard calls instead of creating one
temporary job per stage.

### 3. Fallback is allowed only before the first successful provider response

The job begins on `primary`. If the first attempted invocation cannot start or returns a provider/protocol failure before producing a successful response, the adapter may retry that stage once on the configured fallback and pins it. As soon as any response succeeds, the engine is locked for the rest of the job. Schema-invalid output is repaired on the same engine and never triggers fallback.

Per-stage fallback was rejected because Tier 1 on one model and Tier 2 on another violates the user's single-LLM job model and makes failures/results difficult to interpret.

### 4. Share schema parsing and repair, vary only schema delivery

All structured routes validate with the existing Pydantic schema, strict JSON extraction first, JSON5 tolerance second, and at most one validation-feedback repair turn.

- OMLX receives agno `output_schema`, which emits OpenAI json-schema constrained decoding.
- DeepSeek receives the schema in the prompt/agno JSON-object path, then local validation.
- Claude Code receives `--json-schema <schema>` and also sees the contract in the composed prompt.
- Codex sees the JSON schema in the composed prompt and is locally validated because the pinned CLI lacks an equivalent stage schema flag.

Provider invocation failure and schema failure remain distinct so only the former is eligible for pre-lock fallback.

### 5. Preserve thread-scoped job affinity in radar's producer thread

`info_radar_analysis.run` owns the job context. Its Tier-1 producer uses `contextvars.copy_context()` so the producer and main consumer share the same mutable, lock-protected job state. This retains the current two-slot pipeline overlap while preventing each thread from independently resolving a different engine.

### 6. Runtime API models are separate from static AgentOS model cache

AgentOS and direct agents keep using cached YAML profiles through `get_model`. Production stages build a runtime model client per call from the job's live settings — deliberately uncached, because the cache key would have to carry every preference field and the client is cheap next to the request it makes. OMLX's endpoint/model/parallel limit and DeepSeek's model/reasoning value therefore take effect on the next job without mutating YAML or requiring process restart. Embedders continue to use the static `embedders.local` profile and OMLX endpoint because engine selection concerns LLM stages, not vector compatibility.

What *is* held for the life of a job is the settings themselves, not the clients built from them: `StageJobState` reads both `engine.json` and `coding-agents.json` once at job start. A CLI model re-read per stage would let a settings-page edit land mid-job and score the back half of a batch with a different model than the front half, silently, while the scores are ranked against each other.

### 7. Bound CLI concurrency through the existing provider semaphore registry

`configs/models.yaml` gains `codex_cli` and `claude_cli` concurrency limits. A semaphore is held for the complete child-process invocation. OMLX's live parallel setting updates its stage-call limit at job start; settings changes are rare and affect new acquisitions.

### 8. Make evaluation runs engine-reproducible

`radar_eval.py` and `lang_probe.py` open one stage job for the complete run and
record the selected engine plus frozen runtime settings. Their live LLM calls
all use `run_stage`; prompt assertions call the composition helper without
constructing a static agno model. Prompt digests include engine provenance so results from different
providers/models are not treated as comparable variants.

### 9. Centralize OMLX endpoint resolution below the public model API

`core.omlx.resolve_omlx_endpoint` is the only environment reader. The existing
`models.omlx_endpoint()` public API delegates to it, while live engine defaults
and explicit per-job endpoints use the same resolver without creating a circular
import between `models` and `engine_preferences`.

## Risks / Trade-offs

- **CLI prompts combine system-style instructions and untrusted input in one provider turn** → Keep strong section boundaries, run in an empty ephemeral directory, disable provider tools/customizations mechanically, include the full schema, and validate locally.
- **CLI startup makes short stages slower and costlier than API/OMLX calls** → Preserve Tier-1 batching and provider concurrency; surface provider usage in bridge results without persisting transcripts.
- **A subscription CLI may change flags or event shapes** → Keep image versions pinned, fixture-test argv/protocol parsing, and fail loud on drift.
- **Changing OMLX parallelism while old jobs run can temporarily straddle semaphore generations** → Update only when the value changes; existing holders finish on their original semaphore and new jobs use the new limit.
- **Large knowledge-cleaner output can approach event limits** → Retain the bridge's 262 KiB event bound and existing 64k-character input/output guards; fail the workflow rather than truncate silently.
- **A fallback selected before first success makes the job's actual engine differ from primary** → Pin it for the job and log one structured selection event; never switch again mid-job.

## Migration Plan

1. Add strict engine-state parsing and stage adapter tests using fixture executables.
2. Add provider schema argv support and runtime API-model construction.
3. Replace production workflow agent calls with `run_stage` and wrap top-level jobs in `stage_job`.
4. Rebuild Docker services; existing engine and provider auth volumes require no migration.
5. Rollback consists of reverting workflow call sites to `build_from_name`/`run_structured`; no stored data format changes are involved.

## Open Questions

None blocking. AgentOS interactive routing and durable per-job engine observability are separate future capabilities.
