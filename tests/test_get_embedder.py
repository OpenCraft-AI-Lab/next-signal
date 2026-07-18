"""Embedder helper tests — monkeypatch httpx; no live OMLX required."""

from __future__ import annotations

import pytest

from paca.core import models as models_mod


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text or "ok"

    def json(self) -> dict:
        return self._body


class _FakeClient:
    def __init__(self, response: _FakeResponse | None = None, raise_exc: Exception | None = None):
        self._response = response
        self._raise = raise_exc
        self.calls: list[dict] = []

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def post(self, url: str, *, json: dict, headers: dict) -> _FakeResponse:
        if self._raise is not None:
            raise self._raise
        self.calls.append({"url": url, "json": json, "headers": headers})
        assert self._response is not None
        return self._response


@pytest.fixture
def omlx_env(monkeypatch):
    monkeypatch.setenv("OMLX_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("OMLX_API_KEY", "test-key")


def test_get_embedder_happy_path(omlx_env, monkeypatch) -> None:
    vec = [0.1] * 1024
    body = {"data": [{"embedding": vec}]}
    fake_client = _FakeClient(_FakeResponse(body=body))

    import httpx

    monkeypatch.setattr(httpx, "Client", lambda *a, **kw: fake_client)

    embed = models_mod.get_embedder("local")
    result = embed("hello world")

    assert result == vec
    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call["url"] == "http://localhost:11434/v1/embeddings"
    assert call["json"] == {"input": "hello world", "model": "Qwen3-Embedding-0.6B-8bit"}
    assert call["headers"]["Authorization"] == "Bearer test-key"


def test_get_embedder_unknown_profile_raises(omlx_env) -> None:
    with pytest.raises(KeyError, match="unknown embedder profile 'nope'"):
        models_mod.get_embedder("nope")


def test_get_embedder_http_failure_raises_runtime(omlx_env, monkeypatch) -> None:
    import httpx

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *a, **kw: _FakeClient(raise_exc=httpx.ConnectError("connection refused")),
    )

    embed = models_mod.get_embedder("local")
    with pytest.raises(RuntimeError, match="embedder request failed"):
        embed("hello")


def test_get_embedder_non_200_raises_runtime(omlx_env, monkeypatch) -> None:
    import httpx

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *a, **kw: _FakeClient(_FakeResponse(status_code=500, text="boom")),
    )

    embed = models_mod.get_embedder("local")
    with pytest.raises(RuntimeError, match="embedder returned 500"):
        embed("hello")


def test_get_embedder_malformed_body_raises(omlx_env, monkeypatch) -> None:
    import httpx

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *a, **kw: _FakeClient(_FakeResponse(body={"data": []})),
    )

    embed = models_mod.get_embedder("local")
    with pytest.raises(RuntimeError, match="empty data array"):
        embed("hello")
