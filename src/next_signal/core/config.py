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

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from next_signal.core.paths import CONFIGS_DIR, PROJECT_ROOT, PROMPTS_DIR

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

    A per-provider baseline, not the live selection: which provider actually
    runs — and how a generic endpoint is reached — comes from
    ``~/.next-signal/embedding.json`` (see
    ``next_signal.core.embedding_preferences``). ``dim`` is informational;
    ``next_signal.core.models.get_embedder`` enforces the fixed 1024-value
    contract that keeps ``radar_pushed_topics.embedding`` stable across a
    provider switch.
    """

    model_config = _STRICT

    provider: Literal["omlx", "openai", "openai_compatible"]
    model_id: str
    dim: int


class ModelsConfig(BaseModel):
    model_config = _STRICT

    profiles: dict[str, ModelProfile]
    # Per-provider concurrency limits (see next_signal.core.concurrency).
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
# External coding-agent CLIs
# ---------------------------------------------------------------------------


class CodingAgentProviderConfig(BaseModel):
    model_config = _STRICT

    enabled: bool = True
    timeout_seconds: float = Field(default=1800.0, gt=0)
    max_event_bytes: int = Field(default=262_144, ge=1024)
    max_stderr_chars: int = Field(default=8000, ge=0)
    terminate_grace_seconds: float = Field(default=3.0, gt=0)
    # Names only; values are copied from os.environ at call time.
    inherit_env: list[str] = Field(default_factory=list)


class CodexCliConfig(CodingAgentProviderConfig):
    inherit_user_config: bool = True


class ClaudeCliConfig(CodingAgentProviderConfig):
    bare: bool = False


class CodingAgentProvidersConfig(BaseModel):
    model_config = _STRICT

    codex: CodexCliConfig = Field(default_factory=CodexCliConfig)
    claude: ClaudeCliConfig = Field(default_factory=ClaudeCliConfig)


class CodingAgentProfile(BaseModel):
    model_config = _STRICT

    codex_sandbox: Literal["read-only", "workspace-write"]
    claude_permission_mode: Literal["dontAsk"] = "dontAsk"
    claude_allowed_tools: list[str] = Field(default_factory=list)
    # Production stages process untrusted external content. ``none`` is a
    # hard provider-level tool boundary, not merely a prompt instruction.
    tool_access: Literal["repository", "none"] = "repository"


class CodingAgentsConfig(BaseModel):
    model_config = _STRICT

    allowed_roots: list[str] = Field(min_length=1)
    default_profile: str
    providers: CodingAgentProvidersConfig
    profiles: dict[str, CodingAgentProfile] = Field(min_length=1)

    @model_validator(mode="after")
    def _default_profile_exists(self) -> "CodingAgentsConfig":
        if self.default_profile not in self.profiles:
            raise ValueError(
                f"default_profile {self.default_profile!r} is absent from profiles"
            )
        return self

    def profile(self, name: str | None = None) -> CodingAgentProfile:
        selected = name or self.default_profile
        try:
            return self.profiles[selected]
        except KeyError as e:
            names = ", ".join(sorted(self.profiles))
            raise ValueError(
                f"unknown coding-agent profile {selected!r}; configured profiles: {names}"
            ) from e

    def resolved_allowed_roots(self) -> tuple[Path, ...]:
        roots: list[Path] = []
        for value in self.allowed_roots:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            roots.append(path.resolve())
        return tuple(roots)


def load_coding_agents() -> CodingAgentsConfig:
    return CodingAgentsConfig.model_validate(
        _read_yaml(CONFIGS_DIR / "coding_agents.yaml")
    )


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

    def resolved_instructions(self) -> str:
        if self.instructions:
            return self.instructions
        if self.instructions_file:
            return (PROMPTS_DIR / self.instructions_file).read_text(encoding="utf-8")
        return ""


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
