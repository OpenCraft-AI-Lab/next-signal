"""Embedder snapshot tests — monkeypatch httpx; no live provider required."""

from __future__ import annotations

import json

import pytest

from next_signal.core.secrets import save_secret

from next_signal.core import models as models_mod
from next_signal.core.embedding_preferences import (
    EmbedderNotSelected,
    load_embedding_preferences,
)

VECTOR = [0.1] * 1024
OMLX = {"base_url": "http://localhost:11434/v1", "model": "Qwen3-Embedding-0.6B-8bit"}
COMPATIBLE = {
    "base_url": "https://host.example/v1/",
    "model": "bge-m3",
    "space_id": "house-bge-m3",
}


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, body: object = None, text: str = ""):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = text or "ok"

    def json(self) -> object:
        if isinstance(self._body, Exception):
            raise self._body
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
def state(tmp_path, monkeypatch):
    """Point ``get_embedder()`` at a per-test state file, re-read on every call.

    The real loader and validators still run — only the path moves.
    """
    path = tmp_path / "embedding.json"
    monkeypatch.setattr(
        models_mod,
        "load_embedding_preferences",
        lambda: load_embedding_preferences(path),
    )

    def select(payload: dict) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    return select


@pytest.fixture
def responds(monkeypatch):
    """Install a fake httpx client and hand back its recorded calls."""
    import httpx

    def install(
        body: object = None, *, status_code: int = 200, text: str = "", raise_exc=None
    ) -> _FakeClient:
        if body is None and raise_exc is None:
            body = {"data": [{"embedding": VECTOR}]}
        client = _FakeClient(
            _FakeResponse(status_code=status_code, body=body, text=text),
            raise_exc=raise_exc,
        )
        monkeypatch.setattr(httpx, "Client", lambda *a, **kw: client)
        return client

    return install


def test_nothing_selected_raises_its_own_type(state) -> None:
    """Distinguishable from a failure, so dedup can report it differently."""
    state({})

    with pytest.raises(EmbedderNotSelected, match="No embedder has been selected"):
        models_mod.get_embedder()


def test_omlx_snapshot_uses_its_own_endpoint(state, responds) -> None:
    """Embedding's endpoint, not the engine's — one mlx-lm process, one model."""
    save_secret("OMLX_API_KEY", "test-key")
    state({"provider": "omlx", "omlx": OMLX})
    client = responds()

    snapshot = models_mod.get_embedder()

    assert snapshot.provider == "omlx"
    assert snapshot.identity == "omlx:Qwen3-Embedding-0.6B-8bit"
    assert snapshot.embed("hello world") == VECTOR
    call = client.calls[0]
    assert call["url"] == "http://localhost:11434/v1/embeddings"
    # OMLX's route has no `dimensions` parameter — the shipped model is 1024.
    assert call["json"] == {"input": "hello world", "model": "Qwen3-Embedding-0.6B-8bit"}
    assert call["headers"]["Authorization"] == "Bearer test-key"


def test_openai_snapshot_requests_the_fixed_width(state, responds, monkeypatch) -> None:
    save_secret("RADAR_EMBEDDING_OPENAI_API_KEY", "sk-test")
    state({"provider": "openai", "openai": {"model": "text-embedding-3-large"}})
    client = responds()

    snapshot = models_mod.get_embedder()

    assert snapshot.identity == "openai:text-embedding-3-large"
    assert snapshot.embed("hello") == VECTOR
    call = client.calls[0]
    assert call["url"] == "https://api.openai.com/v1/embeddings"
    assert call["json"]["dimensions"] == 1024
    assert call["headers"]["Authorization"] == "Bearer sk-test"


def test_compatible_snapshot_appends_the_route(state, responds, monkeypatch) -> None:
    save_secret("EMBEDDING_API_KEY", "secret")
    state({"provider": "openai_compatible", "openai_compatible": COMPATIBLE})
    client = responds()

    snapshot = models_mod.get_embedder()

    # The identity names the vector space, never the endpoint that served it.
    assert snapshot.identity == "openai_compatible:house-bge-m3"
    assert snapshot.model_id == "bge-m3"
    assert snapshot.embed("hello") == VECTOR
    call = client.calls[0]
    assert call["url"] == "https://host.example/v1/embeddings"
    assert call["json"]["dimensions"] == 1024
    assert call["headers"]["Authorization"] == "Bearer secret"


def test_openai_without_a_key_names_the_variable(state) -> None:
    state({"provider": "openai", "openai": {"model": "text-embedding-3-small"}})

    with pytest.raises(
        RuntimeError, match="RADAR_EMBEDDING_OPENAI_API_KEY is not configured"
    ):
        models_mod.get_embedder()


def test_compatible_without_its_key_names_that_variable(state) -> None:
    state({"provider": "openai_compatible", "openai_compatible": COMPATIBLE})

    with pytest.raises(RuntimeError, match="EMBEDDING_API_KEY is not configured"):
        models_mod.get_embedder()


@pytest.fixture
def omlx_snapshot(state):
    state({"provider": "omlx", "omlx": OMLX})
    return models_mod.get_embedder


def test_transport_failure_raises_runtime(omlx_snapshot, responds) -> None:
    import httpx

    responds(raise_exc=httpx.ConnectError("connection refused"))
    with pytest.raises(RuntimeError, match="embedder request failed"):
        omlx_snapshot().embed("hello")


def test_non_2xx_raises_runtime(omlx_snapshot, responds) -> None:
    responds({}, status_code=500, text="boom")
    with pytest.raises(RuntimeError, match="embedder returned 500"):
        omlx_snapshot().embed("hello")


@pytest.mark.parametrize(
    ("body", "message"),
    [
        pytest.param(ValueError("not json"), "malformed body", id="unparseable"),
        pytest.param([1, 2, 3], "malformed body", id="not-an-object"),
        pytest.param({"error": "nope"}, "malformed body", id="no-data-key"),
        pytest.param({"data": []}, "empty data array", id="empty-data"),
        pytest.param({"data": [{}]}, "empty data array", id="no-embedding-key"),
        pytest.param(
            {"data": [{"embedding": [0.1] * 1536}]}, "1536 values", id="wrong-width"
        ),
        pytest.param(
            {"data": [{"embedding": "not-a-list"}]}, "non-list", id="not-a-list"
        ),
        pytest.param(
            {"data": [{"embedding": ["x"] + [0.1] * 1023}]},
            "non-numeric value at index 0",
            id="non-numeric",
        ),
        pytest.param(
            {"data": [{"embedding": [float("nan")] + [0.1] * 1023}]},
            "non-finite value at index 0",
            id="nan",
        ),
        pytest.param(
            {"data": [{"embedding": [0.1] * 1023 + [float("inf")]}]},
            "non-finite value at index 1023",
            id="infinity",
        ),
    ],
)
def test_unusable_response_raises_rather_than_degrading(
    omlx_snapshot, responds, body, message
) -> None:
    responds(body)
    with pytest.raises(RuntimeError, match=message):
        omlx_snapshot().embed("hello")
