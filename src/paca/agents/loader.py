"""Build agno Agent instances from YAML configs.

The factory only knows about *generic* agents (model + tools + instructions).
Specialist behavior lives in their YAML + the registered tools they reference.

Shared static context (`prompts/_shared/*.md`) is appended to every agent's
instructions, and the ``SIGNAL_OUTPUT_LANG`` language is either substituted into
the prompt's own ``{{OUTPUT_LANGUAGE}}`` token or appended as a block when the
prompt has none. To opt out, set ``shared_context: false`` /
``output_language: false`` in the agent's YAML — the two flags are independent.
"""

from __future__ import annotations

from agno.agent import Agent

from paca.core.config import AgentConfig, load_agent
from paca.core.context import (
    LANGUAGE_TOKEN,
    language_name,
    language_rule,
    output_language,
    shared_context,
)
from paca.core.db import get_db
from paca.core.models import get_model
from paca.registry import resolve_tools


def build_from_config(cfg: AgentConfig) -> Agent:
    """Assemble an agno.Agent from a parsed AgentConfig.

    Tools are looked up by name in ``paca.registry``. Unknown tool names
    raise — fail loud rather than silently dropping capabilities.
    """
    kwargs = {
        "name": cfg.name,
        "model": get_model(cfg.model_profile),
        "tools": resolve_tools(cfg.tools),
        "instructions": _compose_instructions(cfg),
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


def build_from_name(name: str) -> Agent:
    return build_from_config(load_agent(name))


def _compose_instructions(cfg: AgentConfig) -> str:
    """Compose agent instructions, then shared context, then any language rule.

    Order and delivery are both measured decisions — see design.md D1/D2 in the
    configurable-output-language change.
    """
    own = cfg.resolved_instructions().strip()
    wants_language = cfg.extra.get("output_language") is not False
    lang = output_language() if wants_language else None

    # Substituting in place leaves the prompt's own closing contract last.
    substituted = wants_language and LANGUAGE_TOKEN in own
    if substituted:
        own = own.replace(LANGUAGE_TOKEN, language_name(lang))

    shared = ""
    if cfg.extra.get("shared_context") is not False:
        shared = shared_context().strip()

    # The "# Agent role" heading exists only to separate the agent's prompt from
    # the shared block, so it appears only alongside that block. Adding it
    # unconditionally silently rewrote all ten production agents' prompts once
    # (they all opt out of shared context) and measured +31% tier-2 output.
    sections = ["# Agent role\n\n" + own, "# System rules\n\n" + shared] if shared else [own]

    # Fallback for prompts that do not carry the token: append the block, so
    # turning the setting on still reaches every agent rather than silently
    # skipping the ones nobody has migrated.
    if wants_language and not substituted and lang is not None:
        sections.append(language_rule(lang))

    composed = "\n\n---\n\n".join(sections)

    if LANGUAGE_TOKEN in composed:
        raise RuntimeError(
            f"{cfg.name}: composed instructions still contain {LANGUAGE_TOKEN}. "
            "Usually the prompt declares the token while the agent sets "
            "extra: {output_language: false}; it can also mean the token leaked "
            "into prompts/_shared/."
        )
    return composed
