"""Build agno Agent instances from YAML configs.

The factory only knows about *generic* agents (model + tools + instructions).
Specialist behavior lives in their YAML + the registered tools they reference.

Shared static context (`prompts/_shared/*.md`) is appended to every agent's
instructions, and the resolved output language (see ``next_signal.core.language``) is
either substituted into the prompt's own ``{{OUTPUT_LANGUAGE}}`` token or
appended as a block when the prompt has none. To opt out, set
``shared_context: false`` / ``output_language: off`` (or ``false``) in the
agent's YAML — the two flags are independent.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.models.base import Model

from next_signal.core.config import AgentConfig, load_agent
from next_signal.core.context import shared_context
from next_signal.core.db import get_db
from next_signal.core.language import (
    LANGUAGE_TOKEN,
    language_name,
    language_rule,
    normalize_policy,
    resolve_language,
)
from next_signal.core.models import get_model
from next_signal.registry import resolve_tools


def build_from_config(
    cfg: AgentConfig,
    *,
    language: str | None = None,
    model: Model | None = None,
) -> Agent:
    """Assemble an agno.Agent from a parsed AgentConfig.

    Tools are looked up by name in ``next_signal.registry``. Unknown tool names
    raise — fail loud rather than silently dropping capabilities.

    ``language`` is the per-call override consumed by agents whose policy is
    ``same_as_source`` (e.g. the detected language of one ingested item). It
    has no effect on any other policy.
    """
    kwargs = {
        "name": cfg.name,
        "model": model or get_model(cfg.model_profile),
        "tools": resolve_tools(cfg.tools),
        "instructions": _compose_instructions(cfg, override=language),
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


def build_from_name(name: str, *, language: str | None = None) -> Agent:
    return build_from_config(load_agent(name), language=language)


def _compose_instructions(cfg: AgentConfig, *, override: str | None = None) -> str:
    """Compose agent instructions, then shared context, then any language rule.

    Order and delivery are both measured decisions — see design.md D1/D2 in the
    archived configurable-output-language change, and D1-D9 in
    output-language-policy for the policy generalization.
    """
    own = cfg.resolved_instructions().strip()
    policy = normalize_policy(cfg.extra.get("output_language", "global"))
    lang = resolve_language(policy, override=override)

    # Substituting in place leaves the prompt's own closing contract last.
    substituted = lang is not None and LANGUAGE_TOKEN in own
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
    # a policy that resolves to a language still reaches every agent rather
    # than silently skipping the ones nobody has migrated.
    if lang is not None and not substituted:
        sections.append(language_rule(lang))

    composed = "\n\n---\n\n".join(sections)

    if LANGUAGE_TOKEN in composed:
        raise RuntimeError(
            f"{cfg.name}: composed instructions still contain {LANGUAGE_TOKEN}. "
            "Usually the prompt declares the token while the agent sets "
            "extra: {output_language: off}; it can also mean the token leaked "
            "into prompts/_shared/."
        )
    return composed
