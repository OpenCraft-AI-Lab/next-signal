from __future__ import annotations

import pytest

from next_signal.core.secrets import save_secret

from next_signal.core.models import omlx_endpoint
from next_signal.core.omlx import resolve_omlx_endpoint


def test_public_endpoint_reads_centralized_environment(monkeypatch) -> None:
    monkeypatch.setenv("OMLX_BASE_URL", "http://omlx.test/v1")
    save_secret("OMLX_API_KEY", "secret")

    assert omlx_endpoint() == {
        "base_url": "http://omlx.test/v1",
        "api_key": "secret",
    }


def test_explicit_runtime_url_keeps_centralized_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OMLX_BASE_URL", "http://ignored.test/v1")
    save_secret("OMLX_API_KEY", "secret")

    assert resolve_omlx_endpoint(base_url="http://job.test/v1") == {
        "base_url": "http://job.test/v1",
        "api_key": "secret",
    }


def test_default_url_is_only_used_when_environment_is_absent(monkeypatch) -> None:
    monkeypatch.delenv("OMLX_BASE_URL", raising=False)
    assert resolve_omlx_endpoint(default_base_url="http://default.test/v1")[
        "base_url"
    ] == "http://default.test/v1"


def test_missing_required_endpoint_fails_loudly(monkeypatch) -> None:
    monkeypatch.delenv("OMLX_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="OMLX_BASE_URL not set"):
        omlx_endpoint()
