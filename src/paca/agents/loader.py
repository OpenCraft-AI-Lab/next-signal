"""Build agno Agent instances from YAML configs.

The factory only knows about *generic* agents (model + tools + instructions).
Specialist behavior lives in their YAML + the registered tools they reference.

Shared static context (`prompts/_shared/*.md`) is prepended to every agent's
instructions automatically. To opt out for a specific agent (e.g. a
benchmarking probe), set ``shared_context: false`` in its YAML.
"""

from __future__ import annotations

from agno.agent import Agent

from paca.core.config import DEFAULT_LOCALE, AgentConfig, load_agent
from paca.core.context import shared_context
from paca.core.db import get_db
from paca.core.models import get_model
from paca.registry import resolve_tools


def build_from_config(cfg: AgentConfig, locale: str = DEFAULT_LOCALE) -> Agent:
    """Assemble an agno.Agent from a parsed AgentConfig.

    Tools are looked up by name in ``paca.registry``. Unknown tool names
    raise — fail loud rather than silently dropping capabilities. ``locale``
    selects a per-locale instructions variant (see AgentConfig).
    """
    kwargs = {
        "name": cfg.name,
        "model": get_model(cfg.model_profile),
        "tools": resolve_tools(cfg.tools),
        "instructions": _compose_instructions(cfg, locale),
        "markdown": cfg.markdown,
        "add_history_to_context": cfg.add_history_to_context,
        "num_history_runs": cfg.num_history_runs,
        "enable_session_summaries": cfg.enable_session_summaries,
        "add_session_summary_to_context": cfg.add_session_summary_to_context,
        "add_datetime_to_context": cfg.add_datetime_to_context,
        "telemetry": False,
    }
    if cfg.extra.get("db", True) is not False:
        kwargs["db"] = get_db()
    return Agent(
        **kwargs,
    )


def build_from_name(name: str, locale: str = DEFAULT_LOCALE) -> Agent:
    return build_from_config(load_agent(name), locale)


def _compose_instructions(cfg: AgentConfig, locale: str = DEFAULT_LOCALE) -> str:
    """Combine shared context (house rules, user profile) with per-agent instructions.

    Layout in the resulting prompt:

        # System rules
        <prompts/_shared/*.md concatenated>

        ---

        # Agent role
        <per-agent instructions>
    """
    own = cfg.resolved_instructions(locale).strip()
    if cfg.extra.get("shared_context") is False:
        return own
    shared = shared_context().strip()
    if not shared:
        return own
    return (
        "# System rules\n\n"
        + shared
        + "\n\n---\n\n# Agent role\n\n"
        + own
    )
