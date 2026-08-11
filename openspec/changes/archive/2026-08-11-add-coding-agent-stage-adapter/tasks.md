## 1. Runtime engine state

- [x] 1.1 Add strict Python parsing and configured defaults for `engine.json`, with tests for every engine, fallback validation, absent state, and malformed state.
- [x] 1.2 Add runtime OMLX/DeepSeek stage-model construction and live provider concurrency updates without changing AgentOS's static model cache.

## 2. Provider-neutral stage adapter

- [x] 2.1 Add `stage_job` engine affinity and pre-first-success fallback, including cross-thread context sharing tests.
- [x] 2.2 Add plain and structured `run_stage` paths that preserve agent instructions/language and share strict, JSON5, and one-repair validation.
- [x] 2.3 Extend the Claude bridge invocation to accept Pydantic-derived `--json-schema`; keep Codex schema delivery prompt-only and fixture-test both argv contracts.
- [x] 2.4 Gate full CLI invocations with configured `codex_cli` and `claude_cli` concurrency limits.

## 3. Production workflow migration

- [x] 3.1 Route info-radar Tier 1, Tier 2, and dedup judge calls through one shared stage-job context.
- [x] 3.2 Route radar recap generation through the selected stage adapter.
- [x] 3.3 Route knowledge cleaner, frontmatter, GitHub enrichment, and classifier calls through one shared stage-job context.

## 4. Documentation and verification

- [x] 4.1 Update English and Chinese operations/container/dashboard documentation to state that engine selection now drives production jobs and describe job-scoped fallback.
- [x] 4.2 Run targeted tests, full Python tests, Ruff, strict OpenSpec validation, Dashboard tests/typecheck/build, and Docker composition checks.
- [x] 4.3 Rebuild the image and run a real historical-news production-path smoke for both authenticated CLI engines without overwriting existing analysis rows.

## 5. Review hardening

- [x] 5.1 Isolate untrusted production CLI stages in empty per-run workspaces and enforce no-tools provider argv without changing direct review/edit commands.
- [x] 5.2 Bind direct AgentOS knowledge workflow sync/async/streaming runs to one stage job and test fallback affinity through `build().run()`.
- [x] 5.3 Run radar/language evaluation harnesses through one stage job and persist actual engine/model provenance in their existing outputs.
- [x] 5.4 Centralize all OMLX endpoint resolution and update English/Chinese architecture and module documentation.

## 6. Second review pass

- [x] 6.1 Freeze `CodingAgentPreferences` on `StageJobState` alongside the engine preferences, and pass them explicitly to `run_coding_agent` and to provenance. The runner already accepted a `preferences` argument that nothing supplied, so every CLI stage re-read `coding-agents.json` — pinning the engine while leaving the model it runs free to change mid-job.
- [x] 6.2 Make `_invoke_cli` work under a live event loop. AgentOS reaches the exposed knowledge-ingest workflow through `arun`, and agno runs a sync step executor inline on the loop thread, so `asyncio.run` raised there — caught as a provider failure and answered with the fallback, which reads as a missing CLI rather than a wrong call.
- [x] 6.3 Correct design section 6: runtime stage models are built per call and deliberately *not* cached (`get_stage_model`'s own docstring says so). What a job holds for its lifetime is the settings, not the clients.
- [x] 6.4 Test both: a settings edit landing mid-job must not reach that job's remaining stages or its provenance, and a CLI stage driven from inside `asyncio.run` must return its result rather than failing over.
