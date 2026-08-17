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


class EngineNotSelected(RuntimeError):
    """No engine has been selected, so no production job can run.

    A distinct type rather than a generic error, mirroring
    ``core.embedding_preferences.EmbedderNotSelected`` — a caller can tell
    "nobody has chosen one yet" from "the chosen one is broken" without
    parsing prose. Unlike embedding, there is no degraded mode to fall back
    to: a production stage job's entire purpose is an LLM call, so an
    unselected engine blocks the job rather than being caught and skipped by
    a conservative-default consumer the way the dedup gate handles
    ``EmbedderNotSelected``.
    """


class EnginePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Unset until an operator explicitly saves a selection — `configs/models.yaml`
    # supplies prefill for the omlx/deepseek panes' own fields, never a primary.
    # This mirrors `core.embedding_preferences.EmbeddingPreferences.provider`:
    # nothing this repo could pick on the operator's behalf, so nothing is picked.
    primary: Engine | None = None
    fallback: FallbackEngine
    omlx: OmlxSettings
    deepseek: DeepSeekSettings
    updated_at: str | None = None
    updated_by: str | None = None

    @model_validator(mode="after")
    def _fallback_differs_from_primary(self) -> "EnginePreferences":
        if self.primary is not None and self.fallback == self.primary:
            raise ValueError(f"{self.primary} cannot fall back to itself")
        return self


def configured_engine_defaults(models: ModelsConfig | None = None) -> EnginePreferences:
    """Fresh-install settings: no primary selected, panes prefilled from `models.yaml`.

    `primary` and `fallback` are never derived from `configs/models.yaml` — that
    file's `local` profile is prefill for the OMLX pane's own fields, exactly as
    `embedders.local` is prefill for the Radar Embedding OMLX pane, never a
    runtime default. An operator must explicitly choose and save a primary
    engine before any production stage job can run.
    """
    config = models or load_models()
    local = config.profiles["local"]
    deepseek = config.profiles["deepseek_smart"]

    return EnginePreferences(
        primary=None,
        fallback="none",
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
