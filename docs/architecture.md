# Architecture

> **English** · [中文](./zh/architecture.md)

next-signal (Python package `paca`) is a local-first info-radar + knowledge
framework built on [agno](https://github.com/agno-agi/agno) 2.6+.

## Mental model: a runnable chassis plus capability blocks

This repo is not "a bot". It is **an orchestrator chassis plus a set of runnable
units**:

- **runnable** — agents / workflows / teams, all declared and loaded from
  `configs/{agents,workflows,teams}/`.
- **tools** — agent-facing business actions. Domain tools go in
  `src/paca/tools/<domain>/`; cross-cutting tools sit directly in
  `src/paca/tools/`.
- **integrations** — provider / CLI / HTTP adapters. Domain adapters go in
  `src/paca/integrations/<domain>/`; cross-cutting ones sit directly in
  `src/paca/integrations/`.
- **workflows** — the orchestration layer over agents / tools / stages,
  centralized in `src/paca/workflows/`.

One AgentOS process carries every runnable and tool capability (`paca serve`,
`:7777` — no built-in chat surface is mounted on it today). The CLI reaches the
same workflows and agents through the centralized runnable loader. The Dashboard
is a separate Next.js process that reads Postgres or spawns one-shot `paca` CLI
children; it does **not** require `paca serve` to be running.

## Runtime topology

```text
paca AgentOS FastAPI (:7777)
  - specialist agents / workflows
  - tool registry

CLI -------------------------> runnable loader / workflow run_now
Dashboard (:3000 Next.js) ---> Postgres reads + one-shot `paca` CLI children

shared lower layers:
  model factory (OMLX first, cloud fallback)
  tools -> integrations -> external APIs / CLIs / local state
```

## Code layers

```
src/paca/
  core/              shared infra: config / db / models / paths / logging / context
  agents/loader.py   generic agent assembly (YAML → agno.Agent)
  orchestrator/      runnable loader / workflow tools / runtime assembly
  workflows/         centralized workflow factories; private stages in workflows/stages/<name>/
  teams/             team factories (Python only for complex teams; none shipped today)
  interfaces/        CLI entrypoints
  api/               custom FastAPI routes (planned; empty package today)
  os_app.py          AgentOS runtime assembly entrypoint
  registry.py        tool-surface assembler (registers and resolves every tool)
  tools/             agent-facing tools, grouped by domain: knowledge/
  integrations/      provider adapters, grouped by domain: knowledge/ info_radar/
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
  go in `src/paca/workflows/stages/<workflow>/`.
- `registry.py` / `os_app.py` are assembly modules and sit above the whole stack.
- If you find yourself needing `core` to import `tools`, or an integration to
  import a tool or agent, stop and redesign.

## Key design decisions

| Decision | Why |
|---|---|
| **agno as the framework** | AgentOS ships FastAPI / tracing / sessions / memory — no reason to build our own |
| **A single AgentOS process** | CLI and Dashboard (indirectly) share one set of component definitions; one storage model for traces and sessions |
| **Postgres + pgvector** | Natively supported by agno; pgvector avoids a second vector store; one backup strategy |
| **Behavior defined in YAML** | Dashboard-editable and hot-loadable; readable diffs; Python only defines the shape |
| **Local models first** | Privacy and cost; cloud models are an explicit fallback, not the default |
| **An explicit tool registry** | The LLM-visible tool surface is greppable; no dynamic scanning, because implicit exposure is a security risk |
| **GBrain as an external long-term KB** | markdown-first + hybrid search + automatic graph; not worth rebuilding |
| **Telemetry off** | Local-first means no data leaves the machine (both `AgentOS` and directly constructed `Agent`s must disable it) |

## Non-goals

Deliberately out of scope: multi-user authorization and cloud SaaS, HA and
clustering, near-term Linux/Windows scheduling, reimplementing agno's AgentOS /
tracing / memory, and treating GBrain as an agent operating system.

## Plugging a new capability into the chassis

1. **New agent:** `configs/agents/<name>.yaml` + `prompts/agents/<name>.md`.
2. **New tool:** implement in `src/paca/tools/<domain>/` and expose a stable name
   from that package's `register()`.
3. **New integration:** `src/paca/integrations/<domain>/`, or `src/paca/integrations/`
   if it is cross-cutting.
4. **New workflow:** declare in `configs/workflows/<name>.yaml`; implement a
   factory in `src/paca/workflows/<name>.py` when it is non-trivial.
5. **New team:** declare in `configs/teams/<name>.yaml`; add
   `src/paca/teams/<name>.py` only when routing is complex.
6. **New collector** (periodic CLI data mover, no LLM): implement in
   `src/paca/collectors/<name>/`. Manual runs hook in through a thin shell at
   `src/paca/workflows/<name>.py` (YAML sets `expose.agent_os: false` and points
   `extra.run_now` at the collector entrypoint, invoked by
   `paca run-workflow <name>`).
7. **Analysis workflow on top of a collector** (LLM-driven, consumes the
   collector's business table): implement as a package at
   `src/paca/workflows/<name>_analysis/` with stages split into `stages/`. Agents
   and prompts use the standard YAML/markdown paths, and manual runs hook in
   through the same thin-shell `extra.run_now`. The `seen_at` column belongs to
   the analysis layer — collectors never touch it. Currently shipped:
   `info_radar_analysis`.

Full step-by-step instructions live in the
[development guide](./development.md). Capability contracts live in
[`openspec/specs/`](../openspec/specs/). Deep dives per area (chassis / knowledge
/ info flow / operator console) are in [`docs/modules/`](./modules/core.md).

A full inventory of agents and tools is deliberately **not** maintained in the
docs — `uv run paca list` and `src/paca/registry.py` are the source of truth.
