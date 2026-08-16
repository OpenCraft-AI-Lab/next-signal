"""Runtime LLM engine selection shared with the Dashboard settings page."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from next_signal.core.config import ModelsConfig, load_models
from next_signal.core.paths import STATE_ROOT

Engine = Literal["omlx", "deepseek", "codex_cli", "claude_cli"]
FallbackEngine = Literal["none", "omlx", "deepseek", "codex_cli", "claude_cli"]
DeepSeekReasoning = Literal["off", "low", "high"]

ENGINE_PREFERENCES_FILE = STATE_ROOT / "engine.json"
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_PROVIDER_ENGINE: dict[str, Engine] = {"omlx": "omlx", "deepseek": "deepseek"}


class OmlxSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Unset until an operator points next-signal at a local server. There is no
    # value this repo could ship that would be right, so a fresh install reads
    # as unset and OMLX profiles take their configured `fallback_profile`.
    base_url: str | None = None
    model: str
    parallel: Literal[1, 2, 4]

    @field_validator("base_url")
    @classmethod
    def _valid_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        selected = value.strip()
        if not selected:
            return None
        if not re.fullmatch(r"https?://\S+", selected):
            raise ValueError(f"OMLX endpoint must be an http(s) URL: {selected}")
        return selected

    @field_validator("model")
    @classmethod
    def _valid_model(cls, value: str) -> str:
        selected = value.strip()
        if not _MODEL_ID.fullmatch(selected):
            raise ValueError(f"invalid OMLX model identifier: {selected}")
        return selected


class DeepSeekSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    reasoning: DeepSeekReasoning

    @field_validator("model")
    @classmethod
    def _valid_model(cls, value: str) -> str:
        selected = value.strip()
        if not _MODEL_ID.fullmatch(selected):
            raise ValueError(f"invalid DeepSeek model identifier: {selected}")
        return selected


class EnginePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: Engine
    fallback: FallbackEngine
    omlx: OmlxSettings
    deepseek: DeepSeekSettings
    updated_at: str | None = None
    updated_by: str | None = None

    @model_validator(mode="after")
    def _fallback_differs_from_primary(self) -> "EnginePreferences":
        if self.fallback == self.primary:
            raise ValueError(f"{self.primary} cannot fall back to itself")
        return self


def configured_engine_defaults(models: ModelsConfig | None = None) -> EnginePreferences:
    """Derive fresh-install settings from the same profiles as the Dashboard."""
    config = models or load_models()
    local = config.profiles["local"]
    deepseek = config.profiles["deepseek_smart"]
    fallback_provider = ""
    if local.fallback_profile:
        fallback = config.profiles.get(local.fallback_profile)
        fallback_provider = fallback.provider if fallback else ""

    return EnginePreferences(
        primary=_PROVIDER_ENGINE.get(local.provider, "omlx"),
        fallback=_PROVIDER_ENGINE.get(fallback_provider, "none"),
        omlx=OmlxSettings(
            # No endpoint baseline: the local server's address is the one thing
            # this repo cannot know, so it stays unset until someone saves it.
            base_url=None,
            model=local.model_id,
            parallel=config.concurrency.get("omlx", 2),
        ),
        deepseek=DeepSeekSettings(model=deepseek.model_id, reasoning="low"),
    )


def load_engine_preferences(
    path: Path = ENGINE_PREFERENCES_FILE,
    *,
    defaults: EnginePreferences | None = None,
) -> EnginePreferences:
    """Read live engine state, failing loudly when a present file is unusable."""
    base = defaults or configured_engine_defaults()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return base
    except OSError as exc:
        raise RuntimeError(f"cannot read engine preferences {path}: {exc}") from exc

    try:
        data: Any = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("engine preferences must be an object")
        merged = base.model_dump()
        for section in ("omlx", "deepseek"):
            if section in data:
                value = data[section]
                if not isinstance(value, dict):
                    raise ValueError(f"{section} preferences must be an object")
                merged[section].update(value)
        merged.update({key: value for key, value in data.items() if key not in {"omlx", "deepseek"}})
        return EnginePreferences.model_validate(merged)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f"invalid engine preferences {path}: {exc}") from exc
