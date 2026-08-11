## MODIFIED Requirements

### Requirement: Single AgentOS process

The system SHALL run all agents, teams, and workflows inside a single `agno.os.AgentOS` instance, exposed on port 7777.

#### Scenario: next-signal serve starts the app

- **WHEN** the operator runs `uv run next-signal serve`
- **THEN** a FastAPI app at `http://localhost:7777` exposes agno endpoints for every registered agent, team, and workflow

#### Scenario: telemetry is disabled

- **WHEN** AgentOS is constructed
- **THEN** it is initialized with `telemetry=False` so no data is sent to agno's hosted control plane
