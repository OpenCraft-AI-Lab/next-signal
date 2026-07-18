"""AgentOS entrypoint — the FastAPI app exposed at port 7777.

Run with::

    uv run uvicorn paca.os_app:app --port 7777 --reload

This module is the single registration point. It walks ``configs/agents/``,
``configs/teams/``, and ``configs/workflows/`` to build everything
declaratively, then hands the list to AgentOS.
"""

from __future__ import annotations

from agno.os import AgentOS
from dotenv import load_dotenv

from paca.core.logging import configure as configure_logging
from paca.core.logging import get_logger
from paca.core.paths import ensure_dirs
from paca.orchestrator.runnable_loader import load_runnables

load_dotenv()
configure_logging()
ensure_dirs()
log = get_logger(__name__)


_agents, _teams, _workflows = load_runnables()

agent_os = AgentOS(
    agents=_agents,
    teams=_teams,
    workflows=_workflows,
    # Local-first: don't ping agno's hosted control plane.
    telemetry=False,
)

app = agent_os.get_app()


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("AGENTOS_PORT", "7777"))
    uvicorn.run("paca.os_app:app", host="127.0.0.1", port=port, reload=True)
