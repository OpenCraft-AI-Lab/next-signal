"""Model factory: turns a profile name from ``configs/models.yaml`` into an
agno Model instance.

Every credential named below comes from the credential store
(``next_signal.core.secrets``), never from the environment. Cloud constructors
are handed their key explicitly and raise first when it is missing: agno's model
classes fall back to reading their own provider env var when constructed without
one, which would resolve a credential from a source this system does not read.

Supported providers:
  * ``omlx``     — local mlx-lm OpenAI-compatible server; ``OMLX_BASE_URL`` in
                   ``.env``, optional ``OMLX_API_KEY`` in the credential store.
  * ``claude``   — Anthropic, requires ``ANTHROPIC_API_KEY``.
  * ``openai``   — OpenAI cloud, requires ``OPENAI_API_KEY``.
  * ``gemini``   — Google, requires ``GOOGLE_API_KEY``.
  * ``deepseek`` — DeepSeek, OpenAI-compatible API, requires ``DEEPSEEK_API_KEY``.
                   Base URL defaults to https://api.deepseek.com; override
                   via ``DEEPSEEK_BASE_URL`` in ``.env``.

The factory intentionally keeps the surface tiny: callers ask for a profile
name and get back something that quacks like ``agno.models.base.Model``.
Provider-specific tuning lives in the YAML, not in code.

Embedders live at the bottom of this module and follow a different shape:
``get_embedder()`` takes no profile name and resolves one immutable snapshot
per item from ``~/.next-signal/embedding.json``. See that section's header.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from agno.models.base import Model

from next_signal.core.concurrency import ProviderConcurrency
from next_signal.core.config import ModelProfile, load_models
from next_signal.core.embedding_preferences import (
    embedder_identity,
    load_embedding_preferences,
)
from next_signal.core.engine_preferences import EnginePreferences
from next_signal.core.logging import get_logger
from next_signal.core.omlx import resolve_omlx_endpoint
from next_signal.core.secrets import require_secret

log = get_logger(__name__)

_concurrency_configured = False


def get_model(profile_name: str) -> Model:
    """Build an agno Model from a profile in ``configs/models.yaml``.

    The result is cached per (profile_name) so multiple agents sharing a
    profile share a single underlying client. The first call also configures
    the per-provider concurrency limits.

    If the requested profile fails to build (e.g. OMLX endpoint unreachable)
    and the profile defines a ``fallback_profile``, the fallback is built
    instead. This preserves the design promise that local-first agents stay
    available when the local model is down.
    """
    ensure_concurrency_configured()
    return _build(profile_name)


def ensure_concurrency_configured() -> None:
    global _concurrency_configured
    if not _concurrency_configured:
        ProviderConcurrency.configure(load_models().concurrency)
        _concurrency_configured = True


def get_stage_model(
    engine: str,
    preferences: EnginePreferences,
    *,
    structured: bool,
) -> Model:
    """Build an uncached API model from one job's live engine settings."""
    ensure_concurrency_configured()
    profiles = load_models().profiles
    if engine == "omlx":
        baseline = profiles["local_structured" if structured else "local"]
        profile = baseline.model_copy(update={"model_id": preferences.omlx.model})
        ProviderConcurrency.set_limit("omlx", preferences.omlx.parallel)
        return _wrap_with_concurrency(
            _build_omlx(profile, base_url=preferences.omlx.base_url),
            "omlx",
        )
    if engine == "deepseek":
        baseline = profiles["deepseek_structured" if structured else "deepseek_smart"]
        extra = dict(baseline.extra)
        if preferences.deepseek.reasoning == "off":
            extra.pop("reasoning_effort", None)
            extra["extra_body"] = {"thinking": {"type": "disabled"}}
        else:
            extra["reasoning_effort"] = preferences.deepseek.reasoning
            extra.pop("extra_body", None)
        profile = baseline.model_copy(
            update={"model_id": preferences.deepseek.model, "extra": extra}
        )
        return _wrap_with_concurrency(_build_deepseek(profile), "deepseek")
    raise ValueError(f"stage engine {engine!r} is not an API model provider")


@lru_cache(maxsize=32)
def _build(profile_name: str) -> Model:
    profiles = load_models().profiles
    if profile_name not in profiles:
        raise KeyError(f"unknown model profile {profile_name!r}; have {list(profiles)}")
    profile = profiles[profile_name]
    try:
        model = _build_for_provider(profile)
    except RuntimeError as e:
        # RuntimeError is what _omlx_endpoint raises when local inference is
        # unreachable. KeyError / ValueError (programmer mistakes) propagate.
        if profile.fallback_profile:
            log.warning(
                "model_profile_fallback",
                profile=profile_name,
                fallback=profile.fallback_profile,
                error=str(e),
            )
            return _build(profile.fallback_profile)
        raise
    return _wrap_with_concurrency(model, profile.provider)


def _build_for_provider(p: ModelProfile) -> Model:
    if p.provider == "omlx":
        return _build_omlx(p)
    if p.provider == "claude":
        return _build_claude(p)
    if p.provider == "openai":
        return _build_openai(p)
    if p.provider == "gemini":
        return _build_gemini(p)
    if p.provider == "deepseek":
        return _build_deepseek(p)
    raise ValueError(f"unsupported provider: {p.provider}")


def _wrap_with_concurrency(model: Model, provider: str) -> Model:
    """Gate the model's inference methods through a per-provider semaphore.

    Wraps the four entry points agno uses:

    - ``response`` / ``aresponse`` — single-shot (regular function / coroutine)
    - ``response_stream`` / ``aresponse_stream`` — streaming (sync / async
      generator); semaphore held for the **entire** iteration so we don't
      release while still drawing tokens from the model

    Every code path that goes through the model factory (and thus every agent /
    Team / Workflow / @tool wrapper) inherits the limit automatically.
    """
    response = getattr(model, "response", None)
    aresponse = getattr(model, "aresponse", None)
    response_stream = getattr(model, "response_stream", None)
    aresponse_stream = getattr(model, "aresponse_stream", None)

    if response is not None:
        def wrapped_response(*args, _fn=response, **kwargs):
            with ProviderConcurrency.acquire_sync(provider):
                return _fn(*args, **kwargs)
        wrapped_response.__wrapped__ = response  # type: ignore[attr-defined]
        model.response = wrapped_response  # type: ignore[method-assign]

    if aresponse is not None:
        async def wrapped_aresponse(*args, _fn=aresponse, **kwargs):
            async with ProviderConcurrency.acquire_async(provider):
                return await _fn(*args, **kwargs)
        wrapped_aresponse.__wrapped__ = aresponse  # type: ignore[attr-defined]
        model.aresponse = wrapped_aresponse  # type: ignore[method-assign]

    if response_stream is not None:
        def wrapped_stream(*args, _fn=response_stream, **kwargs):
            # Hold semaphore for the full iteration — release in finally.
            sem = ProviderConcurrency.acquire_sync(provider)
            sem.acquire()
            try:
                yield from _fn(*args, **kwargs)
            finally:
                sem.release()
        wrapped_stream.__wrapped__ = response_stream  # type: ignore[attr-defined]
        model.response_stream = wrapped_stream  # type: ignore[method-assign]

    if aresponse_stream is not None:
        async def wrapped_astream(*args, _fn=aresponse_stream, **kwargs):
            async with ProviderConcurrency.acquire_async(provider):
                async for item in _fn(*args, **kwargs):
                    yield item
        wrapped_astream.__wrapped__ = aresponse_stream  # type: ignore[attr-defined]
        model.aresponse_stream = wrapped_astream  # type: ignore[method-assign]

    return model


# ---------------------------------------------------------------------------
# OMLX — local Qwen3 via mlx-lm OpenAI-compatible server
# ---------------------------------------------------------------------------


def omlx_endpoint() -> dict[str, str]:
    """Return ``{base_url, api_key}`` for the OMLX server.

    Single source of truth — anywhere else that needs to talk to OMLX must
    call this rather than re-reading ``OMLX_*`` env vars directly. See
    design.md §3.10.
    """
    return resolve_omlx_endpoint()


def _build_omlx(p: ModelProfile, *, base_url: str | None = None) -> Model:
    """OMLX serves an OpenAI-compatible API; we use agno's OpenAILike adapter
    plus a few Qwen3-specific knobs (disable thinking, sampling tweaks).
    """
    from agno.models.openai.like import OpenAILike

    ep = resolve_omlx_endpoint(base_url=base_url) if base_url else omlx_endpoint()
    extra_body: dict[str, Any] = {
        "chat_template_kwargs": {"enable_thinking": False},
        "top_k": 20,
        "min_p": 0.05,
    }
    extra_body.update(p.extra.get("extra_body", {}))

    return OpenAILike(
        id=p.model_id,
        base_url=ep["base_url"],
        api_key=ep["api_key"] or "not-needed",
        temperature=p.temperature,
        top_p=p.top_p,
        max_tokens=p.max_tokens,
        timeout=p.timeout,
        extra_body=extra_body,
        # OMLX honors OpenAI-standard `response_format` json_schema (xgrammar
        # constrained decoding); agno emits it only for agents that pass an
        # `output_schema`. Native structured outputs stay off — mlx-lm's own
        # path is uneven; the json_schema path is the one we use.
        supports_native_structured_outputs=False,
        supports_json_schema_outputs=True,
    )


# ---------------------------------------------------------------------------
# Cloud providers — thin wrappers; tuning stays in YAML.
# ---------------------------------------------------------------------------


def _build_claude(p: ModelProfile) -> Model:
    from agno.models.anthropic import Claude

    return Claude(
        id=p.model_id,
        api_key=require_secret("ANTHROPIC_API_KEY"),
        temperature=p.temperature,
        max_tokens=p.max_tokens,
    )


def _build_openai(p: ModelProfile) -> Model:
    from agno.models.openai import OpenAIChat

    return OpenAIChat(
        id=p.model_id,
        api_key=require_secret("OPENAI_API_KEY"),
        temperature=p.temperature,
        top_p=p.top_p,
        max_tokens=p.max_tokens,
    )


def _build_gemini(p: ModelProfile) -> Model:
    from agno.models.google import Gemini

    return Gemini(
        id=p.model_id,
        api_key=require_secret("GOOGLE_API_KEY"),
        temperature=p.temperature,
        top_p=p.top_p,
        max_output_tokens=p.max_tokens,
    )


def _build_deepseek(p: ModelProfile) -> Model:
    from agno.models.openai.like import OpenAILike

    api_key = require_secret("DEEPSEEK_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    extra_body: dict[str, Any] = dict(p.extra.get("extra_body", {}))

    return OpenAILike(
        id=p.model_id,
        base_url=base_url,
        api_key=api_key,
        temperature=p.temperature,
        top_p=p.top_p,
        max_tokens=p.max_tokens,
        timeout=p.timeout,
        # deepseek-v4-flash/-pro default to thinking mode on with effort "high"
        # (undocumented in code before; caught us with slower/pricier calls).
        # YAML sets this via `extra.reasoning_effort` ("low"/"high"/"max") or
        # fully disables thinking via `extra.extra_body.thinking.type: disabled`.
        reasoning_effort=p.extra.get("reasoning_effort"),
        extra_body=extra_body or None,
        # DeepSeek's API rejects response_format json_schema ("This response_format
        # type is unavailable now"); only json_object mode is supported. Both flags
        # off makes agno emit {"type": "json_object"} — the schema is conveyed via
        # the prompt and enforced by run_structured's parse/validate/repair pass.
        supports_native_structured_outputs=False,
        supports_json_schema_outputs=False,
    )


def reset_cache() -> None:
    """Drop cached model instances. Called by hot-reload after YAML edits."""
    _build.cache_clear()


# ---------------------------------------------------------------------------
# Embedders — provider-neutral, one immutable snapshot per item
# ---------------------------------------------------------------------------
#
# Unlike LLM profiles, an embedder is not addressed by name: the live selection
# is whatever ``~/.next-signal/embedding.json`` says at the moment an item
# starts, and ``configs/models.yaml::embedders`` only supplies each provider's
# baseline. ``get_embedder()`` reads that state and the credential store exactly
# once and freezes the answer into a ``ResolvedEmbedder``, so a settings write
# landing mid-request cannot relabel a vector that is already in flight —
# the consumer stores ``snapshot.identity``, never a fresh read.

EMBEDDING_DIMENSIONS = 1024
OPENAI_API_ROOT = "https://api.openai.com/v1"


@dataclass(frozen=True)
class ResolvedEmbedder:
    """One item's embedder: what produced the vector, and how to produce it."""

    provider: str
    model_id: str
    identity: str
    embed: Callable[[str], list[float]]


def get_embedder() -> ResolvedEmbedder:
    """Freeze the live embedding selection into one immutable snapshot.

    Reads ``embedding.json`` and the credential for the selected provider once,
    here — not inside ``embed()`` — so every call on the returned object talks to
    the same endpoint under the same identity.

    There is no fallback: providers are not substitutable, and quietly embedding
    into a different vector space would park the selected provider's dedup memory
    without saying so. Missing credentials, transport errors, non-2xx responses,
    malformed bodies, and wrong-shaped vectors all raise ``RuntimeError``; the
    info-radar dedup gate owns the conservative policy (log loud, treat as novel,
    store no topic row).

    Each ``embed`` call takes ``ProviderConcurrency`` for its own provider, so
    OMLX embedding queues behind OMLX inference on the single local GPU while a
    hosted provider never consumes that slot.
    """
    ensure_concurrency_configured()
    prefs = load_embedding_preferences()
    provider = prefs.provider

    if provider == "omlx":
        endpoint = omlx_endpoint()
        model_id = prefs.omlx.model
        url = endpoint["base_url"].rstrip("/") + "/embeddings"
        api_key = endpoint["api_key"]
        # OMLX's route has no `dimensions` parameter and the shipped model
        # already emits 1024 values; a model that does not is caught on response.
        dimensions: int | None = None
    elif provider == "openai":
        model_id = prefs.openai.model
        url = f"{OPENAI_API_ROOT}/embeddings"
        api_key = require_secret("OPENAI_API_KEY")
        dimensions = EMBEDDING_DIMENSIONS
    else:
        compatible = prefs.openai_compatible
        model_id = compatible.model
        url = f"{compatible.base_url}/embeddings"
        api_key = require_secret(compatible.api_key_env)
        dimensions = EMBEDDING_DIMENSIONS

    def embed(text: str) -> list[float]:
        return _post_embedding(
            url,
            provider=provider,
            model_id=model_id,
            api_key=api_key,
            dimensions=dimensions,
            text=text,
        )

    return ResolvedEmbedder(
        provider=provider,
        model_id=model_id,
        identity=embedder_identity(prefs),
        embed=embed,
    )


def _post_embedding(
    url: str,
    *,
    provider: str,
    model_id: str,
    api_key: str,
    dimensions: int | None,
    text: str,
) -> list[float]:
    import httpx

    payload: dict[str, Any] = {"input": text, "model": model_id}
    if dimensions is not None:
        payload["dimensions"] = dimensions
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with ProviderConcurrency.acquire_sync(provider):
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise RuntimeError(f"embedder request failed ({url}): {e}") from e
    if resp.status_code >= 400:
        raise RuntimeError(
            f"embedder returned {resp.status_code} from {url}: {resp.text[:200]}"
        )
    try:
        data = resp.json()["data"]
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError(f"embedder returned malformed body from {url}: {e}") from e
    if not data or "embedding" not in data[0]:
        raise RuntimeError(f"embedder returned empty data array: {resp.text[:200]}")
    return _validated_vector(data[0]["embedding"], url)


def _validated_vector(raw: Any, url: str) -> list[float]:
    """Accept exactly ``EMBEDDING_DIMENSIONS`` finite numbers, or raise.

    Never truncates, pads, or normalizes. ``radar_pushed_topics.embedding`` is
    ``vector(1024)`` and the column survives provider switches only because a
    model that cannot produce that width is rejected here rather than reshaped.
    """
    if not isinstance(raw, list):
        raise RuntimeError(f"embedder returned a non-list embedding from {url}")
    if len(raw) != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"embedder returned {len(raw)} values from {url}; exactly "
            f"{EMBEDDING_DIMENSIONS} are required — this model cannot back "
            "radar_pushed_topics.embedding"
        )
    vector: list[float] = []
    for index, value in enumerate(raw):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(
                f"embedder returned a non-numeric value at index {index} "
                f"from {url}: {value!r}"
            )
        number = float(value)
        if not math.isfinite(number):
            raise RuntimeError(
                f"embedder returned a non-finite value at index {index} "
                f"from {url}: {number}"
            )
        vector.append(number)
    return vector
