# core-agent-os

Single-process agno `AgentOS` (FastAPI) that hosts all agents, teams, and workflows.

## Purpose

All user interfaces (Dashboard, CLI) resolve the same agents, teams, and workflows through one runnable loader. State (sessions, memory, traces) lives in local Postgres + pgvector.

## Requirements

### Requirement: Single AgentOS process

The system SHALL run all agents, teams, and workflows inside a single `agno.os.AgentOS` instance, exposed on port 7777.

#### Scenario: paca serve starts the app

- **WHEN** the operator runs `uv run paca serve`
- **THEN** a FastAPI app at `http://localhost:7777` exposes agno endpoints for every registered agent, team, and workflow

#### Scenario: telemetry is disabled

- **WHEN** AgentOS is constructed
- **THEN** it is initialized with `telemetry=False` so no data is sent to agno's hosted control plane

### Requirement: Components loaded from configs at startup

`os_app` SHALL build agents, teams, and workflows from `configs/{agents,teams,workflows}/*.yaml` at process start via the centralized runnable loader, not from hard-coded Python.

#### Scenario: new agent appears after restart

- **WHEN** a new `configs/agents/<name>.yaml` is added and the process restarts
- **THEN** the agent is registered and reachable via the AgentOS HTTP routes

#### Scenario: new workflow appears after restart

- **WHEN** a new enabled `configs/workflows/<name>.yaml` with `expose.agent_os: true` is added and the process restarts
- **THEN** the workflow is registered and reachable via the AgentOS HTTP routes

#### Scenario: disabled team is skipped

- **WHEN** `configs/teams/personal_assistant.yaml` sets `enabled: false`
- **THEN** the team config remains listable but is not registered in AgentOS

#### Scenario: a single bad config does not block startup

- **WHEN** one agent YAML fails to load
- **THEN** the error is logged and the remaining agents/teams/workflows still load
