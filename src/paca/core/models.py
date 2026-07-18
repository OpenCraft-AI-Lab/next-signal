"""Model factory: turns a profile name from ``configs/models.yaml`` into an
agno Model instance.

Supported providers:
  * ``omlx``     — local mlx-lm OpenAI-compatible server, endpoint configured
                   via ``OMLX_BASE_URL`` + ``OMLX_API_KEY`` in ``.env``.
  * ``claude``   — Anthropic, requires ``ANTHROPIC_API_KEY``.
  * ``openai``   — OpenAI cloud, requires ``OPENAI_API_KEY``.
  * ``gemini``   — Google, requires ``GOOGLE_API_KEY``.
  * ``deepseek`` — DeepSeek, OpenAI-compatible API, requires ``DEEPSEEK_API_KEY``.
                   Base URL defaults to https://api.deepseek.com; override
                   via ``DEEPSEEK_BASE_URL`` in ``.env``.

The factory intentionally keeps the surface tiny: callers ask for a profile
name and get back something that quacks like ``agno.models.base.Model``.
Provider-specific tuning lives in the YAML, not in code.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from agno.models.base import Model

from paca.core.concurrency import ProviderConcurrency
from paca.core.config import ModelProfile, load_models
from paca.core.logging import get_logger

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
    _ensure_concurrency_configured()
    return _build(profile_name)


def _ensure_concurrency_configured() -> None:
    global _concurrency_configured
    if not _concurrency_configured:
        ProviderConcurrency.configure(load_models().concurrency)
        _concurrency_configured = True


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
    base_url = os.environ.get("OMLX_BASE_URL")
    if not base_url:
        raise RuntimeError(
            "OMLX_BASE_URL not set. Either set OMLX_BASE_URL (and OMLX_API_KEY) "
            "in .env, or use a non-omlx model profile."
        )
    return {"base_url": base_url, "api_key": os.environ.get("OMLX_API_KEY", "")}


def _build_omlx(p: ModelProfile) -> Model:
    """OMLX serves an OpenAI-compatible API; we use agno's OpenAILike adapter
    plus a few Qwen3-specific knobs (disable thinking, sampling tweaks).
    """
    from agno.models.openai.like import OpenAILike

    ep = omlx_endpoint()
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
        temperature=p.temperature,
        max_tokens=p.max_tokens,
    )


def _build_openai(p: ModelProfile) -> Model:
    from agno.models.openai import OpenAIChat

    return OpenAIChat(
        id=p.model_id,
        temperature=p.temperature,
        top_p=p.top_p,
        max_tokens=p.max_tokens,
    )


def _build_gemini(p: ModelProfile) -> Model:
    from agno.models.google import Gemini

    return Gemini(
        id=p.model_id,
        temperature=p.temperature,
        top_p=p.top_p,
        max_output_tokens=p.max_tokens,
    )


def _build_deepseek(p: ModelProfile) -> Model:
    from agno.models.openai.like import OpenAILike

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY not set. Add it to .env to use the deepseek provider."
        )
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return OpenAILike(
        id=p.model_id,
        base_url=base_url,
        api_key=api_key,
        temperature=p.temperature,
        top_p=p.top_p,
        max_tokens=p.max_tokens,
        timeout=p.timeout,
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
# Embedders — OMLX OpenAI-compatible /v1/embeddings only
# ---------------------------------------------------------------------------


def get_embedder(profile_name: str = "local"):
    """Return ``embed(text: str) -> list[float]`` for the named embedder profile.

    The default profile name is ``local`` and is expected to point at OMLX's
    OpenAI-compatible ``/v1/embeddings`` endpoint (see ``configs/models.yaml``
    section ``embedders:``). Connection failures raise ``RuntimeError`` so
    callers can decide their own fallback policy — see design.md §D5 for the
    info-radar-analysis policy (treat as novel + log loud).

    Each ``embed`` call goes through ``ProviderConcurrency.acquire_sync`` for
    the embedder's provider so it shares the same per-provider cap as
    LLM calls — local OMLX is one GPU and overlapping LLM + embedding
    inference would starve both.

    The dimensionality of the returned vector is whatever the server returns;
    callers that persist into a fixed-dim column must validate length
    themselves.
    """
    _ensure_concurrency_configured()
    profiles = load_models().embedders
    if profile_name not in profiles:
        raise KeyError(
            f"unknown embedder profile {profile_name!r}; "
            f"have {list(profiles)}; add it under embedders: in configs/models.yaml"
        )
    profile = profiles[profile_name]
    # `provider` is Literal["omlx"] in pydantic, so any other value would
    # have failed validation. No runtime branch needed today; when we add a
    # second provider this becomes a dispatch.
    provider = profile.provider

    ep = omlx_endpoint()
    model_id = profile.model_id

    def embed(text: str) -> list[float]:
        import httpx

        url = ep["base_url"].rstrip("/") + "/embeddings"
        headers = {"Content-Type": "application/json"}
        if ep["api_key"]:
            headers["Authorization"] = f"Bearer {ep['api_key']}"
        with ProviderConcurrency.acquire_sync(provider):
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        url,
                        json={"input": text, "model": model_id},
                        headers=headers,
                    )
            except httpx.HTTPError as e:
                raise RuntimeError(f"embedder request failed ({url}): {e}") from e
        if resp.status_code >= 400:
            raise RuntimeError(
                f"embedder returned {resp.status_code} from {url}: {resp.text[:200]}"
            )
        try:
            data = resp.json()["data"]
        except (KeyError, ValueError) as e:
            raise RuntimeError(f"embedder returned malformed body: {e}") from e
        if not data or "embedding" not in data[0]:
            raise RuntimeError(f"embedder returned empty data array: {resp.text[:200]}")
        return list(data[0]["embedding"])

    return embed
