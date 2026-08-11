"""Runtime embedding provider selection shared with the Dashboard settings page.

The three providers are peers to the operator but not on disk. ``omlx`` and
``openai`` have real baselines in ``configs/models.yaml`` under ``embedders:``,
so a partial section here inherits the missing fields from there.
``openai_compatible`` describes an endpoint this repo has never seen — there is
no truthful universal URL, model, key-variable name, or vector space for it —
so its section is optional and, once present, complete.

Nothing in this file ever holds a credential: the compatible section stores the
*name* of an environment variable, and the value is read from the process
environment when ``next_signal.core.models.get_embedder`` resolves an item.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from next_signal.core.config import ModelsConfig, load_models
from next_signal.core.paths import STATE_ROOT

EmbeddingProvider = Literal["omlx", "openai", "openai_compatible"]

EMBEDDING_PREFERENCES_FILE = STATE_ROOT / "embedding.json"
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_API_KEY_ENV = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SPACE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
# The two sections with a `models.yaml` baseline, so a partial state file can
# inherit the rest. The compatible section is deliberately absent.
_MERGED_SECTIONS = ("omlx", "openai")


def _valid_model_id(value: str, provider: str) -> str:
    selected = value.strip()
    if not _MODEL_ID.fullmatch(selected):
        raise ValueError(f"invalid {provider} embedding model identifier: {selected}")
    return selected


class OmlxEmbeddingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str

    @field_validator("model")
    @classmethod
    def _valid_model(cls, value: str) -> str:
        return _valid_model_id(value, "OMLX")


class OpenAIEmbeddingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str

    @field_validator("model")
    @classmethod
    def _valid_model(cls, value: str) -> str:
        return _valid_model_id(value, "OpenAI")


class OpenAICompatibleEmbeddingSettings(BaseModel):
    """One operator-supplied OpenAI-shaped endpoint, described in full.

    ``space_id`` is the logical name of the vector space this endpoint produces.
    It is separate from ``model`` because two endpoints can advertise the same
    model name while differing in weights, tokenizer, pooling, or quantization —
    comparing those vectors would silently suppress genuinely novel items.
    """

    model_config = ConfigDict(extra="forbid")

    base_url: str
    model: str
    api_key_env: str
    space_id: str

    @field_validator("base_url")
    @classmethod
    def _valid_base_url(cls, value: str) -> str:
        selected = value.strip()
        parsed = urlparse(selected)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"embedding base URL must be an http(s) URL: {selected}")
        if not parsed.hostname:
            raise ValueError(f"embedding base URL must name a host: {selected}")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            # A credential smuggled through the URL would be persisted in state,
            # which is the one thing this file promises never to hold.
            raise ValueError(
                "embedding base URL must be a plain API root — userinfo, query, "
                f"and fragment components are rejected: {selected}"
            )
        root = selected.rstrip("/")
        if root.endswith("/embeddings"):
            raise ValueError(
                "embedding base URL is an API root, not the /embeddings route; "
                f"drop the trailing route: {selected}"
            )
        return root

    @field_validator("model")
    @classmethod
    def _valid_model(cls, value: str) -> str:
        return _valid_model_id(value, "OpenAI-compatible")

    @field_validator("api_key_env")
    @classmethod
    def _valid_api_key_env(cls, value: str) -> str:
        selected = value.strip()
        if not _API_KEY_ENV.fullmatch(selected):
            raise ValueError(
                "api_key_env stores an environment variable NAME: 1-64 uppercase "
                f"letters, digits, or underscores, starting with a letter: {selected}"
            )
        return selected

    @field_validator("space_id")
    @classmethod
    def _valid_space_id(cls, value: str) -> str:
        selected = value.strip()
        if not _SPACE_ID.fullmatch(selected):
            raise ValueError(
                "space_id must be 1-128 letters, digits, dots, underscores, or "
                f"hyphens, starting with a letter or digit: {selected}"
            )
        return selected


class EmbeddingPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: EmbeddingProvider
    omlx: OmlxEmbeddingSettings
    openai: OpenAIEmbeddingSettings
    openai_compatible: OpenAICompatibleEmbeddingSettings | None = None
    updated_at: str | None = None
    updated_by: str | None = None

    @model_validator(mode="after")
    def _selected_provider_is_configured(self) -> "EmbeddingPreferences":
        if self.provider == "openai_compatible" and self.openai_compatible is None:
            raise ValueError(
                "openai_compatible is selected but has no saved configuration; "
                "save base_url, model, api_key_env, and space_id before selecting it"
            )
        return self


def configured_embedding_defaults(
    models: ModelsConfig | None = None,
) -> EmbeddingPreferences:
    """Derive fresh-install settings from the same profiles as the Dashboard."""
    config = models or load_models()
    return EmbeddingPreferences(
        provider="omlx",
        omlx=OmlxEmbeddingSettings(model=config.embedders["local"].model_id),
        openai=OpenAIEmbeddingSettings(model=config.embedders["openai"].model_id),
    )


def load_embedding_preferences(
    path: Path = EMBEDDING_PREFERENCES_FILE,
    *,
    defaults: EmbeddingPreferences | None = None,
) -> EmbeddingPreferences:
    """Read live embedding state, failing loudly when a present file is unusable."""
    base = defaults or configured_embedding_defaults()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return base
    except OSError as exc:
        raise RuntimeError(f"cannot read embedding preferences {path}: {exc}") from exc

    try:
        data: Any = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("embedding preferences must be an object")
        merged = base.model_dump()
        for section in _MERGED_SECTIONS:
            if section in data:
                value = data[section]
                if not isinstance(value, dict):
                    raise ValueError(f"{section} preferences must be an object")
                merged[section].update(value)
        # `openai_compatible` lands here whole: it has no baseline to merge
        # against, so a partial section fails validation rather than silently
        # completing itself from values this repo would have had to invent.
        merged.update(
            {key: value for key, value in data.items() if key not in _MERGED_SECTIONS}
        )
        return EmbeddingPreferences.model_validate(merged)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f"invalid embedding preferences {path}: {exc}") from exc


def embedder_identity(prefs: EmbeddingPreferences) -> str:
    """The stable vector-space id stored beside every embedding it produces.

    Physical endpoints stay out of it: moving one compatible service from
    ``127.0.0.1`` to ``host.docker.internal`` must not park its dedup memory.
    """
    if prefs.provider == "omlx":
        return f"omlx:{prefs.omlx.model}"
    if prefs.provider == "openai":
        return f"openai:{prefs.openai.model}"
    # `_selected_provider_is_configured` guarantees the section exists whenever
    # this provider is the selected one.
    return f"openai_compatible:{prefs.openai_compatible.space_id}"
