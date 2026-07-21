"""YAML-backed configuration loaded into Pydantic models.

Layout under ``configs/``::

    models.yaml              # provider profiles
    agents/<name>.yaml       # one per specialist agent
    workflows/<name>.yaml    # one per workflow
    teams/<name>.yaml        # one per team

The dashboard edits these files; loaders below also serve as the source
of truth for the hot-reload mechanism.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from paca.core.paths import CONFIGS_DIR, PROMPTS_DIR

log = logging.getLogger(__name__)

# System default locale, used when a caller builds an agent without naming one.
# Prompt files resolve ``<stem>.<locale><ext>`` first (e.g. radar_x.en.md,
# radar_x.zh.md) and fall back to the unsuffixed ``<stem><ext>`` for
# single-language agents. See core-agents spec.
DEFAULT_LOCALE = "en"

# Reject unknown YAML keys across every config schema. Typo'd keys (e.g.
# `instuctions:` instead of `instructions:`) must fail loudly rather than
# being silently ignored — see design.md §3.4. The dedicated ``extra: dict``
# field on each model is the explicit escape hatch for forward-compat data.
_STRICT = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ModelProfile(BaseModel):
    """One row in ``configs/models.yaml`` under ``profiles``."""

    model_config = _STRICT

    provider: Literal["omlx", "claude", "openai", "gemini", "deepseek"]
    model_id: str
    temperature: float = 0.4
    top_p: float = 0.9
    max_tokens: int | None = None
    # Per-request wall-clock cap in seconds. Preferred over ``max_tokens`` for
    # OMLX structured-output profiles: Alibaba documents that setting
    # ``max_tokens`` with structured output can truncate JSON mid-string, so
    # we let xgrammar terminate naturally and use ``timeout`` as the runaway
    # guard instead. ``None`` keeps the openai SDK default.
    timeout: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    fallback_profile: str | None = None  # graceful degradation


class EmbedderProfile(BaseModel):
    """One row in ``configs/models.yaml`` under ``embedders``.

    Only the local OMLX OpenAI-compatible ``/v1/embeddings`` endpoint is
    supported today. ``dim`` is informational — the actual stored vector
    length is whatever the server returns; the radar_pushed_topics column
    is fixed at vector(1024) for the default Qwen3-Embedding-0.6B-8bit model.
    """

    model_config = _STRICT

    provider: Literal["omlx"]
    model_id: str
    dim: int


class ModelsConfig(BaseModel):
    model_config = _STRICT

    profiles: dict[str, ModelProfile]
    # Per-provider concurrency limits (see paca.core.concurrency).
    # Local providers (omlx) want strict caps; cloud providers get a generous
    # cap as a defensive guard — far above typical use, so it doesn't bite
    # under normal load but prevents a runaway loop from blasting the API.
    concurrency: dict[str, int] = Field(
        default_factory=lambda: {"omlx": 2, "claude": 64, "openai": 64, "gemini": 32}
    )
    embedders: dict[str, EmbedderProfile] = Field(default_factory=dict)


def load_models() -> ModelsConfig:
    return ModelsConfig.model_validate(_read_yaml(CONFIGS_DIR / "models.yaml"))


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """One ``configs/agents/<name>.yaml`` file."""

    model_config = _STRICT

    name: str
    kind: Literal["agent"] = "agent"
    enabled: bool = True
    description: str = ""
    model_profile: str
    tools: list[str] = Field(default_factory=list)
    instructions_file: str | None = None
    instructions: str | None = None  # inline alternative
    markdown: bool = True
    add_history_to_context: bool = True
    num_history_runs: int | None = None
    enable_session_summaries: bool = False
    add_session_summary_to_context: bool | None = None
    add_datetime_to_context: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)

    def resolved_instructions(self, locale: str = DEFAULT_LOCALE) -> str:
        if self.instructions:
            return self.instructions
        if self.instructions_file:
            return _read_instructions_file(self.instructions_file, locale)
        return ""


def _read_instructions_file(rel_path: str, locale: str) -> str:
    """Read a prompt file, preferring the ``<stem>.<locale><ext>`` variant.

    Multi-language agents ship one file per locale (``radar_x.zh.md`` /
    ``radar_x.en.md``); single-language agents ship only the unsuffixed
    ``radar_x.md``, used as the fallback when no locale variant exists.
    ``instructions_file`` names the logical base stem — for a multi-language
    agent no unsuffixed file exists on disk, only the suffixed variants.
    Missing both the variant and the base is a loud error.
    """
    base = PROMPTS_DIR / rel_path
    variant = base.parent / f"{base.stem}.{locale}{base.suffix}"
    if variant.exists():
        return variant.read_text(encoding="utf-8")
    if base.exists():
        return base.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"no instructions file for {rel_path!r} (locale={locale!r}): "
        f"tried {variant.name} and {base.name}"
    )


def load_agent(name: str) -> AgentConfig:
    cfg = AgentConfig.model_validate(_read_yaml(CONFIGS_DIR / "agents" / f"{name}.yaml"))
    if cfg.name != name:
        # Loaders, registries, and the dashboard all key agents by file stem;
        # if the YAML's `name:` field disagrees, two parts of the system
        # would silently disagree on what the agent is called. Force them
        # to match. Same convention applies to workflow YAMLs.
        raise ValueError(
            f"agent file stem {name!r} disagrees with `name:` field {cfg.name!r}; "
            "they must match (use snake_case in both)."
        )
    return cfg


def list_agents() -> list[str]:
    return sorted(p.stem for p in (CONFIGS_DIR / "agents").glob("*.yaml"))


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


class WorkflowConfig(BaseModel):
    model_config = _STRICT

    name: str
    kind: Literal["workflow"] = "workflow"
    enabled: bool = True
    description: str = ""
    factory: str
    expose: "WorkflowExposeConfig" = Field(default_factory=lambda: WorkflowExposeConfig())
    inputs_schema: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class WorkflowToolExposeConfig(BaseModel):
    model_config = _STRICT

    enabled: bool = False
    name: str | None = None


class WorkflowExposeConfig(BaseModel):
    model_config = _STRICT

    agent_os: bool = True
    tool: WorkflowToolExposeConfig = Field(default_factory=WorkflowToolExposeConfig)


def load_workflow(name: str) -> WorkflowConfig:
    cfg = WorkflowConfig.model_validate(
        _read_yaml(CONFIGS_DIR / "workflows" / f"{name}.yaml")
    )
    if cfg.name != name:
        raise ValueError(
            f"workflow file stem {name!r} disagrees with `name:` field {cfg.name!r}; "
            "they must match (use snake_case in both)."
        )
    return cfg


def list_workflows() -> list[str]:
    return sorted(p.stem for p in (CONFIGS_DIR / "workflows").glob("*.yaml"))


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


class TeamConfig(BaseModel):
    model_config = _STRICT

    name: str
    kind: Literal["team"] = "team"
    enabled: bool = True
    description: str = ""
    mode: str = "route"
    members: list[str] = Field(default_factory=list)
    instructions_file: str | None = None
    instructions: str | None = None
    factory: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def resolved_instructions(self) -> str:
        if self.instructions:
            return self.instructions
        if self.instructions_file:
            return (PROMPTS_DIR / self.instructions_file).read_text(encoding="utf-8")
        return ""


def load_team(name: str) -> TeamConfig:
    cfg = TeamConfig.model_validate(_read_yaml(CONFIGS_DIR / "teams" / f"{name}.yaml"))
    if cfg.name != name:
        raise ValueError(
            f"team file stem {name!r} disagrees with `name:` field {cfg.name!r}; "
            "they must match (use snake_case in both)."
        )
    return cfg


def list_teams() -> list[str]:
    return sorted(p.stem for p in (CONFIGS_DIR / "teams").glob("*.yaml"))


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"config file missing: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level must be a mapping, got {type(data).__name__}")
    return data
