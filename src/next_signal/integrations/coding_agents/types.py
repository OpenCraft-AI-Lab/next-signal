"""Stable internal and CLI-facing contracts for coding-agent runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

ProviderName: TypeAlias = Literal["codex", "claude"]

_STRICT = ConfigDict(extra="forbid")


class CodingAgentRunRequest(BaseModel):
    model_config = _STRICT

    provider: ProviderName
    prompt: str = Field(min_length=1)
    cwd: Path
    profile: str | None = None
    json_schema: dict[str, Any] | None = None


class CodingAgentEvent(BaseModel):
    model_config = _STRICT

    type: Literal["event"] = "event"
    provider: ProviderName
    session_id: str | None = None
    event: dict[str, Any]


class CodingAgentResult(BaseModel):
    model_config = _STRICT

    type: Literal["result"] = "result"
    ok: bool
    provider: ProviderName
    session_id: str | None = None
    text: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    returncode: int | None = None
    duration_ms: int = 0
    timed_out: bool = False
    stderr: str = ""
    error: str | None = None


@dataclass
class ProviderParseState:
    """Mutable state populated by one provider's JSONL event parser."""

    session_id: str | None = None
    text: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    terminal_seen: bool = False
    terminal_ok: bool = False
    error: str | None = None
