"""Centralized runnable loading for AgentOS."""

from __future__ import annotations

import importlib
from typing import Any, Callable

from paca.agents.loader import build_from_name
from paca.core.config import (
    WorkflowConfig,
    list_agents,
    list_teams,
    list_workflows,
    load_agent,
    load_team,
    load_workflow,
)
from paca.core.logging import get_logger

log = get_logger(__name__)


def load_agents() -> list[Any]:
    """Build all enabled agents from config."""
    agents: list[Any] = []
    for name in list_agents():
        try:
            cfg = load_agent(name)
            if not cfg.enabled:
                continue
            agents.append(build_from_name(name))
            log.info("agent_loaded", name=name)
        except Exception as e:  # noqa: BLE001
            log.error("agent_load_failed", name=name, error=str(e))
    if not agents:
        raise RuntimeError("no agents loaded; refusing to start AgentOS")
    return agents


def load_workflows() -> list[Any]:
    """Build all enabled AgentOS-exposed workflows from config."""
    workflows: list[Any] = []
    for name in list_workflows():
        try:
            cfg = load_workflow(name)
            if not cfg.enabled or not cfg.expose.agent_os:
                continue
            workflows.append(build_workflow_from_config(cfg))
            log.info("workflow_loaded", name=name)
        except Exception as e:  # noqa: BLE001
            log.error("workflow_load_failed", name=name, error=str(e))
    return workflows


def load_teams() -> list[Any]:
    """Build all enabled teams from config."""
    teams: list[Any] = []
    for name in list_teams():
        try:
            cfg = load_team(name)
            if not cfg.enabled:
                continue
            if not cfg.factory:
                log.warning("team_skipped_no_factory", name=name)
                continue
            teams.append(load_factory(cfg.factory)(cfg))
            log.info("team_loaded", name=name)
        except Exception as e:  # noqa: BLE001
            log.error("team_load_failed", name=name, error=str(e))
    return teams


def load_runnables() -> tuple[list[Any], list[Any], list[Any]]:
    """Return AgentOS agents, teams, and workflows."""
    agents = load_agents()
    teams = load_teams()
    workflows = load_workflows()
    return agents, teams, workflows


def build_workflow_from_config(cfg: WorkflowConfig):
    """Build one workflow using its configured Python factory."""
    factory = load_factory(cfg.factory)
    return factory()


def load_factory(ref: str) -> Callable[..., Any]:
    module_name, sep, attr = ref.partition(":")
    if not sep or not module_name or not attr:
        raise RuntimeError(f"factory must be '<module>:<callable>', got {ref!r}")
    module = importlib.import_module(module_name)
    factory = getattr(module, attr)
    if not callable(factory):
        raise RuntimeError(f"factory is not callable: {ref}")
    return factory
