"""Runtime embedding provider selection shared with the Dashboard settings page.

Nothing is selected until an operator selects it. An absent file, or a present
one naming no provider, is the *unselected* state — a valid resting state, not a
fault. ``configs/models.yaml::embedders`` supplies suggested values for a
provider someone is configuring; it is form prefill and never decides what runs.
A section is therefore complete or invalid, with nothing to inherit.

Nothing here ever holds a credential, or even names one: each provider's key is
located in the credential store under a fixed name.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from next_signal.core.paths import STATE_ROOT

EmbeddingProvider = Literal["omlx", "openai", "openai_compatible"]

EMBEDDING_PREFERENCES_FILE = STATE_ROOT / "embedding.json"
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_SPACE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class EmbedderNotSelected(RuntimeError):
    """No embedding provider has been selected yet.

    A distinct type rather than a message so a caller can tell "nobody has
    chosen one" from "the chosen one is broken" without parsing prose. The
    info-radar dedup gate reports the two differently.
    """


def _valid_model_id(value: str, provider: str) -> str:
    selected = value.strip()
    if not _MODEL_ID.fullmatch(selected):
        raise ValueError(f"invalid {provider} embedding model identifier: {selected}")
    return selected


def _valid_api_root(value: str) -> str:
    """An http(s) API root with no route and no way to smuggle a credential."""
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


class OmlxEmbeddingSettings(BaseModel):
    """A local OMLX embedding server.

    Its own endpoint, not the engine section's: one mlx-lm process serves one
    model, so a chat model and an embedding model are two addresses.
    """

    model_config = ConfigDict(extra="forbid")

    base_url: str
    model: str

    @field_validator("base_url")
    @classmethod
    def _valid_base_url(cls, value: str) -> str:
        return _valid_api_root(value)

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
    space_id: str

    @field_validator("base_url")
    @classmethod
    def _valid_base_url(cls, value: str) -> str:
        return _valid_api_root(value)

    @field_validator("model")
    @classmethod
    def _valid_model(cls, value: str) -> str:
        return _valid_model_id(value, "OpenAI-compatible")

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

    provider: EmbeddingProvider | None = None
    omlx: OmlxEmbeddingSettings | None = None
    openai: OpenAIEmbeddingSettings | None = None
    openai_compatible: OpenAICompatibleEmbeddingSettings | None = None
    updated_at: str | None = None
    updated_by: str | None = None

    @property
    def selected(self) -> bool:
        """Whether an operator has chosen an embedder."""
        return self.provider is not None

    @model_validator(mode="after")
    def _selected_provider_is_configured(self) -> "EmbeddingPreferences":
        if self.provider is not None and getattr(self, self.provider) is None:
            raise ValueError(
                f"{self.provider} is selected but has no saved configuration; "
                "save its settings before selecting it"
            )
        return self


def load_embedding_preferences(
    path: Path = EMBEDDING_PREFERENCES_FILE,
) -> EmbeddingPreferences:
    """Read live embedding state, failing loudly when a present file is unusable.

    An absent file is the unselected state. A present file is validated whole:
    with no baseline to inherit from, a partial section is an error rather than
    something this loader silently completes.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return EmbeddingPreferences()
    except OSError as exc:
        raise RuntimeError(f"cannot read embedding preferences {path}: {exc}") from exc

    try:
        data: Any = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("embedding preferences must be an object")
        return EmbeddingPreferences.model_validate(data)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f"invalid embedding preferences {path}: {exc}") from exc


def embedder_identity(prefs: EmbeddingPreferences) -> str | None:
    """The stable vector-space id stored beside every embedding it produces.

    ``None`` while unselected. Physical endpoints stay out of it: moving one
    compatible service from ``127.0.0.1`` to ``host.docker.internal`` must not
    park its dedup memory.
    """
    if prefs.provider == "omlx":
        return f"omlx:{prefs.omlx.model}"
    if prefs.provider == "openai":
        return f"openai:{prefs.openai.model}"
    if prefs.provider == "openai_compatible":
        return f"openai_compatible:{prefs.openai_compatible.space_id}"
    return None
