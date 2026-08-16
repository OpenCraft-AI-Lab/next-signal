from __future__ import annotations

import pytest

from next_signal.core.secrets import save_secret

from next_signal.core import omlx as omlx_mod
from next_signal.core.engine_preferences import (
    DeepSeekSettings,
    EnginePreferences,
    OmlxSettings,
)
from next_signal.core.models import omlx_endpoint
from next_signal.core.omlx import resolve_omlx_endpoint


def _engine(base_url: str | None) -> EnginePreferences:
    return EnginePreferences(
        primary="omlx",
        fallback="deepseek",
        omlx=OmlxSettings(base_url=base_url, model="qwen", parallel=2),
        deepseek=DeepSeekSettings(model="deepseek-v4-flash", reasoning="low"),
    )


@pytest.fixture
def engine_state(monkeypatch):
    """Point the resolver at an in-memory engine selection."""

    def use(base_url: str | None) -> None:
        monkeypatch.setattr(
            omlx_mod, "load_engine_preferences", lambda: _engine(base_url), raising=False
        )
        monkeypatch.setattr(
            "next_signal.core.engine_preferences.load_engine_preferences",
            lambda: _engine(base_url),
        )

    return use


def test_public_endpoint_reads_the_saved_engine_selection(engine_state) -> None:
    engine_state("http://omlx.test/v1")
    save_secret("OMLX_API_KEY", "secret")

    assert omlx_endpoint() == {
        "base_url": "http://omlx.test/v1",
        "api_key": "secret",
    }


def test_explicit_runtime_url_keeps_centralized_api_key(engine_state) -> None:
    engine_state("http://ignored.test/v1")
    save_secret("OMLX_API_KEY", "secret")

    assert resolve_omlx_endpoint(base_url="http://job.test/v1") == {
        "base_url": "http://job.test/v1",
        "api_key": "secret",
    }


def test_the_environment_is_not_an_endpoint_source(engine_state, monkeypatch) -> None:
    """A leftover .env value must not resurrect an endpoint nobody saved."""
    monkeypatch.setenv("OMLX_BASE_URL", "http://stale.test/v1")
    engine_state(None)

    with pytest.raises(RuntimeError, match="No local OMLX endpoint is configured"):
        omlx_endpoint()


def test_missing_required_endpoint_fails_loudly(engine_state) -> None:
    engine_state(None)
    with pytest.raises(RuntimeError, match="No local OMLX endpoint is configured"):
        omlx_endpoint()
