# Architecture

> **English** · [中文](./zh/architecture.md)

next-signal (Python package `next_signal`) is a local-first info-radar + knowledge
framework built on [agno](https://github.com/agno-agi/agno) 2.6+.

## Mental model: a runnable chassis plus capability blocks

This repo is not "a bot". It is **an orchestrator chassis plus a set of runnable
units**:

- **runnable** — agents / workflows / teams, all declared and loaded from
  `configs/{agents,workflows,teams}/`.
- **tools** — agent-facing business actions. Domain tools go in
  `src/next_signal/tools/<domain>/`; cross-cutting tools sit directly in
  `src/next_signal/tools/`.
- **integrations** — provider / CLI / HTTP adapters. Domain adapters go in
  `src/next_signal/integrations/<domain>/`; cross-cutting ones sit directly in
  `src/next_signal/integrations/`.
- **workflows** — the orchestration layer over agents / tools / stages,
  centralized in `src/next_signal/workflows/`.

One AgentOS process carries every runnable and tool capability (`next-signal serve`,
`:7777` — no built-in chat surface is mounted on it today). The CLI reaches the
same workflows and agents through the centralized runnable loader. The Dashboard
is a separate Next.js process that reads Postgres or spawns one-shot `next-signal` CLI
children; it does **not** require `next-signal serve` to be running.

## Runtime topology

```text
next-signal AgentOS FastAPI (:7777)
  - specialist agents / workflows
  - tool registry

CLI -------------------------> runnable loader / workflow run_now
Dashboard (:3000 Next.js) ---> Postgres reads + one-shot `next-signal` CLI children
Scheduler (no ports) --------> polls the wall clock, fires the radar chain

shared lower layers:
  production stage adapter -> selected OMLX / DeepSeek / Codex CLI / Claude CLI
  static AgentOS model factory (YAML profiles)
  tools -> integrations -> external APIs / CLIs / local state
```

Three long-running processes, and only the third acts on its own. The scheduler
re-reads `~/.next-signal/schedule.json` and the `schedule_state` table on every
poll and runs `info_radar_pull` → `info_radar_analysis` when a configured time
comes due. **It is the only path that spends model tokens with nobody typing a
command**, which is why its state is durable and its settings are read fresh
rather than captured at startup.

## Code layers

```
src/next_signal/
  core/              config / db / models / engine preferences / OMLX resolver / paths
                     clock.py   one local day boundary, shared by every surface
                     schedule.py  reads the schedule state file; loud on a bad one
  agents/loader.py   generic interactive-agent assembly (YAML → agno.Agent)
  agents/stage.py    production LLM routing + whole-job engine affinity/fallback
  orchestrator/      runnable loader / workflow tools / runtime assembly
                     schedule.py  the wall-clock poll loop and its durable state
                     run_now.py   resolves a workflow's manual entry point by name
  workflows/         centralized workflow factories; private stages in workflows/stages/<name>/
  teams/             team factories (Python only for complex teams; none shipped today)
  interfaces/        CLI entrypoints
  api/               custom FastAPI routes (planned; empty package today)
  os_app.py          AgentOS runtime assembly entrypoint
  registry.py        tool-surface assembler (registers and resolves every tool)
  tools/             agent-facing tools, grouped by domain: knowledge/
  integrations/      provider adapters, grouped by domain: knowledge/ info_radar/
                     coding_agents/ (bounded subprocess supervision + auth for the
                     optional Codex / Claude Code CLIs)
  collectors/        periodic CLI data movers (no LLM, no agent caller, write business tables)
                     e.g. info_radar/ writes radar_items; the analysis layer above it lives in
                     workflows/info_radar_analysis/, consumes that table and writes
                     radar_analyses + radar_pushed_topics
```

**Placement follows responsibility, not call convenience.** `tools/` is the
surface an agent can see; `integrations/` is the low-level external-system
adapter; `workflows/` is the centralized orchestration layer. Domain capabilities
may be organized into subdirectories, but workflows never move into a domain tool
directory — that is how orchestration logic gets scattered.

## Runtime state files

Behavior lives in `configs/*.yaml`, which ships inside the image. Anything the
operator changes *while the stack is running* lives in `~/.next-signal/` instead
— a Docker volume, hand-editable, and writable by a process that cannot write the
image:

| File | Written by | Read by |
|---|---|---|
| `language.json` | settings page | agents whose output-language policy is `global` |
| `engine.json` | settings page | every production LLM stage, at job start |
| `coding-agents.json` | settings page | CLI stages and `coding-agent run`, at job start |
| `schedule.json` | settings page | the scheduler, on every 30s poll |
| `embedding.json` | settings page | the dedup gate, once per item |

Three properties hold for all of them, and each is load-bearing:

- **Read at call time, never at import.** A dashboard edit takes effect without a
  restart, and a missing file cannot break startup.
- **Loud on the pipeline side, forgiving on the dashboard side.** The Python
  reader raises on a malformed file; the dashboard's falls back and logs, because
  it renders the panel an operator would use to repair it. Booleans are checked
  rather than coerced — `bool("false")` is `True`, and these files are edited by
  hand.
- **Frozen for the length of a job, not per stage.** A job reads `engine.json`
  and `coding-agents.json` once and reuses both. A radar job runs for tens of
  minutes over a batch whose scores are ranked against each other, so a mid-job
  re-read would score its two halves with different models.

`embedding.json` is the exception to that last property, and for the same
underlying reason. A vector is not an opinion that can be revised — it is stored,
and it is only comparable to vectors from the same embedder — so switching
provider must take effect promptly rather than at the next job boundary. The
gate therefore resolves one immutable snapshot **per item**: provider, model,
endpoint, credential, and a stable vector-space identity, frozen together before
the request goes out. That identity is what `radar_pushed_topics.embedder`
stores and what the search filters on, so a settings write landing between an
embedding response and its row cannot label a vector with a space it did not
come from. The next item picks up the new selection. `core-embedding` owns the
identity string; no other layer derives one.

The one setting deliberately *not* here is the timezone. `INFO_RADAR_TIMEZONE`
is an environment variable because the same value fixes scheduling, radar day
grouping, and review due dates; a schedule carrying its own zone would fire at
08:00 in one zone while its results were filed under a day boundary drawn in
another.

## Dependency direction

Dependencies point strictly downward. Reverse imports are not allowed:

```text
interfaces / api
  -> orchestrator
  -> workflows / teams / agents
  -> tools
  -> integrations
  -> core
```

Hard rules:

- `core` imports nothing from any layer above it.
- `tools` may orchestrate `integrations` (downward is fine); `integrations` never
  import `tools` or agents.
- Workflows may compose agents / tools / private stages; workflow-private helpers
  go in `src/next_signal/workflows/stages/<workflow>/`.
- `registry.py` / `os_app.py` are assembly modules and sit above the whole stack.
- If you find yourself needing `core` to import `tools`, or an integration to
  import a tool or agent, stop and redesign.

Production LLM stages are a deliberate second path beside interactive AgentOS
agents. Workflows call `run_stage`, while direct interactive agents still use
`build_from_name`. The AgentOS-exposed knowledge workflow wraps sync, async, and
streaming execution in one stage-job context. CLI stages are one-shot model
workers, not agno models: each receives a composed prompt in an empty temporary
directory under a no-tools provider profile, so untrusted article content cannot
turn into repository inspection or commands.

## Key design decisions

| Decision | Why |
|---|---|
| **agno as the framework** | AgentOS ships FastAPI / tracing / sessions / memory — no reason to build our own |
| **A single AgentOS process** | CLI and Dashboard (indirectly) share one set of component definitions; one storage model for traces and sessions |
| **Postgres + pgvector** | Natively supported by agno; pgvector avoids a second vector store; one backup strategy |
| **Behavior defined in YAML** | Dashboard-editable and hot-loadable; readable diffs; Python only defines the shape |
| **Local models first** | Privacy and cost; cloud models are an explicit fallback, not the default |
| **One production engine per job** | Dashboard state selects one provider for every LLM stage; fallback is allowed only before the first successful response, and the model settings are frozen when the job opens |
| **Runtime state in `~/.next-signal/`, behavior in `configs/`** | The repo tree inside the container is image-baked; anything the dashboard writes has to live on a volume, and gets read at call time so no restart is needed |
| **One wall-clock scheduler, state in Postgres** | A laptop sleeps and Docker gets quit, so the loop re-derives what it owes from the clock and a durable slot on every poll rather than holding a timer |
| **An explicit tool registry** | The LLM-visible tool surface is greppable; no dynamic scanning, because implicit exposure is a security risk |
| **GBrain as an external long-term KB** | markdown-first + hybrid search + automatic graph; not worth rebuilding |
| **Framework telemetry off** | AgentOS/agno usage telemetry is disabled; selected cloud/API/CLI engines may still send stage prompts to their provider |

## Non-goals

Deliberately out of scope: multi-user authorization and cloud SaaS, HA and
clustering, host-level scheduling (cron / launchd / Task Scheduler — the
scheduler is a container, so the platform split never has to be confronted),
cron expressions and weekday filters, reimplementing agno's AgentOS / tracing /
memory, and treating GBrain as an agent operating system.

## Plugging a new capability into the chassis

1. **New agent:** `configs/agents/<name>.yaml` + `prompts/agents/<name>.md`.
2. **New tool:** implement in `src/next_signal/tools/<domain>/` and expose a stable name
   from that package's `register()`.
3. **New integration:** `src/next_signal/integrations/<domain>/`, or `src/next_signal/integrations/`
   if it is cross-cutting.
4. **New workflow:** declare in `configs/workflows/<name>.yaml`; implement a
   factory in `src/next_signal/workflows/<name>.py` when it is non-trivial.
5. **New team:** declare in `configs/teams/<name>.yaml`; add
   `src/next_signal/teams/<name>.py` only when routing is complex.
6. **New collector** (periodic CLI data mover, no LLM): implement in
   `src/next_signal/collectors/<name>/`. Manual runs hook in through a thin shell at
   `src/next_signal/workflows/<name>.py` (YAML sets `expose.agent_os: false` and points
   `extra.run_now` at the collector entrypoint, invoked by
   `next-signal run-workflow <name>`).
7. **Analysis workflow on top of a collector** (LLM-driven, consumes the
   collector's business table): implement as a package at
   `src/next_signal/workflows/<name>_analysis/` with stages split into `stages/`. Agents
   and prompts use the standard YAML/markdown paths, and manual runs hook in
   through the same thin-shell `extra.run_now`. The `seen_at` column belongs to
   the analysis layer — collectors never touch it. Currently shipped:
   `info_radar_analysis`.

Full step-by-step instructions live in the
[development guide](./development.md). Capability contracts live in
[`openspec/specs/`](../openspec/specs/). Deep dives per area (chassis / knowledge
/ info flow / operator console) are in [`docs/modules/`](./modules/core.md).

A full inventory of agents and tools is deliberately **not** maintained in the
docs — `uv run next-signal list` and `src/next_signal/registry.py` are the source of truth.
