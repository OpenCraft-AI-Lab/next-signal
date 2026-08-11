"""Live operator defaults for external coding-agent CLIs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from next_signal.core.paths import STATE_ROOT

CODING_AGENT_PREFERENCES_FILE = STATE_ROOT / "coding-agents.json"

_STRICT = ConfigDict(extra="forbid")
_CODEX_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")
_CLAUDE_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]-]{0,511}")


class CodexPreferences(BaseModel):
    """Explicit Codex selections required before next-signal may invoke it."""

    model_config = _STRICT

    model: str
    model_reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"]
    service_tier: Literal["default", "fast"]

    @field_validator("model")
    @classmethod
    def _valid_model_id(cls, value: str) -> str:
        if not _CODEX_MODEL_ID.fullmatch(value):
            raise ValueError(
                "model must be 1-128 letters, numbers, dots, underscores, colons, "
                "slashes, or hyphens"
            )
        return value


class ClaudePreferences(BaseModel):
    """Explicit Claude selections required before next-signal may invoke it."""

    model_config = _STRICT

    model: str
    effort: Literal["low", "medium", "high", "xhigh", "max"]

    @field_validator("model")
    @classmethod
    def _valid_model_id(cls, value: str) -> str:
        if not _CLAUDE_MODEL_ID.fullmatch(value):
            raise ValueError(
                "Claude model must be 1-512 letters, numbers, dots, underscores, "
                "colons, slashes, brackets, or hyphens"
            )
        return value


class CodingAgentPreferences(BaseModel):
    """Versionless runtime-state payload shared with the Dashboard."""

    model_config = _STRICT

    codex: CodexPreferences | None = None
    claude: ClaudePreferences | None = None
    updated_at: str | None = None
    updated_by: str | None = None

    @field_validator("codex", mode="before")
    @classmethod
    def _empty_legacy_codex_is_unset(cls, value):
        return None if value == {} else value

    @field_validator("claude", mode="before")
    @classmethod
    def _empty_legacy_claude_is_unset(cls, value):
        return None if value == {} else value


def load_coding_agent_preferences(
    path: Path = CODING_AGENT_PREFERENCES_FILE,
) -> CodingAgentPreferences:
    """Read live preferences; absent inherits provider defaults, malformed fails loud."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return CodingAgentPreferences()
    except OSError as exc:
        raise RuntimeError(f"could not read {path}: {exc}") from exc

    try:
        data = json.loads(raw)
        return CodingAgentPreferences.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError(f"{path} is invalid: {exc}") from exc
