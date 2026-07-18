# Project Context

## What this is

`next-signal` (Python package `paca`) — a local-first info-radar + knowledge
pipeline on agno 2.6+. One AgentOS process hosts every agent, team, and
workflow; CLI / Dashboard / launchd all call the same capability surface.

## Shape

Orchestrator chassis + runnable units:

- **Chassis** (`src/paca/core`, `agents`, `orchestrator`, `interfaces`,
  `scheduler`, `api`, `os_app.py`).
- **Runnables** (`configs/agents`, `configs/workflows`, `configs/teams`) with
  implementations in `src/paca/agents`, `src/paca/workflows`, and `src/paca/teams`.
- **Capabilities**: agent-facing tools in `src/paca/tools/<domain>/`; provider
  adapters in `src/paca/integrations/<domain>/`.

Dependencies move downward only: workflows/agents/teams -> tools -> integrations -> core.

## Conventions

- Always run Python through `uv` (`uv run pytest -q`, `uv run paca ...`).
- Agent/workflow/team behavior lives in `configs/` YAML; Python defines the shape.
- Tools are registered explicitly through `src/paca/registry.py` and package-level
  `tools/<domain>/register()` hooks.
- Tests: prefer fixtures + real calls over mocks; integration tests skip by default.

## Spec layout

`openspec/specs/` is flat (OpenSpec requirement); module grouping is by name
prefix: `core-*` (chassis), `knowledge-*`, `info-filter-*`.

## Human docs

Architecture, development, operations, and per-module docs live in
[`../docs/`](../docs/). This file is the AI-facing context for OpenSpec work.
