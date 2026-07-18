"""Tests for the get_model fallback chain (OMLX down -> fallback_profile).

The design promise (CLAUDE.md / docs): when the local OMLX endpoint is
unreachable the factory catches RuntimeError and builds the profile named in
``fallback_profile``; after recovery, ``reset_cache()`` is required before
OMLX is retried (the fallback result is lru-cached).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from paca.core import models as models_mod
from paca.core.config import ModelProfile


@pytest.fixture(autouse=True)
def _fresh_cache():
    models_mod.reset_cache()
    yield
    models_mod.reset_cache()


class _Marker:
    """Stand-in model; has none of the four response methods so the
    concurrency wrapper leaves it untouched."""

    def __init__(self, provider: str) -> None:
        self.provider = provider


def _patch_profiles(monkeypatch, profiles: dict[str, ModelProfile]) -> None:
    fake_cfg = SimpleNamespace(profiles=profiles, concurrency={})
    monkeypatch.setattr(models_mod, "load_models", lambda: fake_cfg)


def test_unknown_profile_raises_keyerror(monkeypatch) -> None:
    _patch_profiles(monkeypatch, {})
    with pytest.raises(KeyError, match="unknown model profile"):
        models_mod.get_model("nope")


def test_omlx_unreachable_falls_back_to_cloud(monkeypatch) -> None:
    _patch_profiles(
        monkeypatch,
        {
            "local": ModelProfile(provider="omlx", model_id="qwen", fallback_profile="cloud"),
            "cloud": ModelProfile(provider="claude", model_id="claude-x"),
        },
    )

    def fake_build(p: ModelProfile):
        if p.provider == "omlx":
            raise RuntimeError("OMLX_BASE_URL not set")
        return _Marker(p.provider)

    monkeypatch.setattr(models_mod, "_build_for_provider", fake_build)

    assert models_mod.get_model("local").provider == "claude"


def test_no_fallback_propagates_runtime_error(monkeypatch) -> None:
    _patch_profiles(
        monkeypatch, {"local": ModelProfile(provider="omlx", model_id="qwen")}
    )
    monkeypatch.setattr(
        models_mod,
        "_build_for_provider",
        lambda p: (_ for _ in ()).throw(RuntimeError("endpoint down")),
    )

    with pytest.raises(RuntimeError, match="endpoint down"):
        models_mod.get_model("local")


def test_recovery_needs_reset_cache_before_omlx_is_retried(monkeypatch) -> None:
    _patch_profiles(
        monkeypatch,
        {
            "local": ModelProfile(provider="omlx", model_id="qwen", fallback_profile="cloud"),
            "cloud": ModelProfile(provider="claude", model_id="claude-x"),
        },
    )
    omlx_up = {"v": False}

    def fake_build(p: ModelProfile):
        if p.provider == "omlx" and not omlx_up["v"]:
            raise RuntimeError("unreachable")
        return _Marker(p.provider)

    monkeypatch.setattr(models_mod, "_build_for_provider", fake_build)

    assert models_mod.get_model("local").provider == "claude"

    omlx_up["v"] = True
    # Still the cached fallback — recovery alone must not flip the profile.
    assert models_mod.get_model("local").provider == "claude"

    models_mod.reset_cache()
    assert models_mod.get_model("local").provider == "omlx"


def test_build_deepseek_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        models_mod._build_deepseek(
            ModelProfile(provider="deepseek", model_id="deepseek-v4-flash")
        )


def test_build_deepseek_uses_json_object_mode(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    model = models_mod._build_deepseek(
        ModelProfile(provider="deepseek", model_id="deepseek-v4-flash")
    )
    assert model.id == "deepseek-v4-flash"
    assert model.base_url == "https://api.deepseek.com"
    # DeepSeek only supports json_object; both flags off so run_structured carries
    # the schema via prompt + validate/repair rather than json_schema decoding.
    assert model.supports_json_schema_outputs is False
    assert model.supports_native_structured_outputs is False


def test_build_deepseek_honors_base_url_override(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://proxy.example.com")
    model = models_mod._build_deepseek(
        ModelProfile(provider="deepseek", model_id="deepseek-v4-flash")
    )
    assert model.base_url == "https://proxy.example.com"
