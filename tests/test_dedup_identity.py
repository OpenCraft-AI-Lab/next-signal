"""The dedup gate must persist the identity that produced the vector.

A settings write can land at any instant, including between an embedding
response and the row that stores it. These tests pin the property that makes
that harmless: one snapshot is resolved per item, and everything downstream of
the embedding call uses *that* snapshot rather than re-reading live state.
"""

from __future__ import annotations

import json

import pytest

from next_signal.core import models as models_mod
from next_signal.core.embedding_preferences import load_embedding_preferences
from next_signal.workflows.info_radar_analysis.stages import dedup as dedup_mod

VECTOR = [0.1] * 1024
_ENDPOINT = "http://localhost:11434/v1"
A = {"provider": "omlx", "omlx": {"base_url": _ENDPOINT, "model": "embed-A"}}
B = {"provider": "omlx", "omlx": {"base_url": _ENDPOINT, "model": "embed-B"}}


class _FakeClient:
    def __init__(self, calls: list[dict]):
        self._calls = calls

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def post(self, url: str, *, json: dict, headers: dict):  # noqa: ARG002
        self._calls.append({"url": url, "model": json["model"]})
        return _FakeResponse()


class _FakeResponse:
    status_code = 200
    text = "ok"

    def json(self) -> dict:
        return {"data": [{"embedding": VECTOR}]}


@pytest.fixture
def live_state(tmp_path, monkeypatch):
    """A rewritable state file that every ``get_embedder()`` call re-reads."""
    path = tmp_path / "embedding.json"
    monkeypatch.setattr(
        models_mod,
        "load_embedding_preferences",
        lambda: load_embedding_preferences(path),
    )

    def write(payload: dict) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    return write


@pytest.fixture
def embed_calls(monkeypatch):
    import httpx

    calls: list[dict] = []
    monkeypatch.setattr(httpx, "Client", lambda *a, **kw: _FakeClient(calls))
    return calls


def test_state_change_mid_item_cannot_relabel_its_vector(
    live_state, embed_calls, monkeypatch
) -> None:
    live_state(A)
    searched: list[str] = []

    def swap_state_then_search(embedding, *, embedder, k, threshold):  # noqa: ARG001
        # The operator saves a new provider while this item is in flight.
        searched.append(embedder)
        live_state(B)
        return []

    monkeypatch.setattr(dedup_mod.analysis_store, "search_topics", swap_state_then_search)

    outcome = dedup_mod.run("a summary")

    assert searched == ["omlx:embed-A"]
    assert outcome.embedder == "omlx:embed-A"
    assert outcome.embedding == VECTOR
    assert embed_calls[0]["model"] == "embed-A"
    # The next item picks up the new selection — the switch is not lost, just
    # not applied retroactively to a vector that already exists.
    assert models_mod.get_embedder().identity == "omlx:embed-B"


def test_duplicate_verdict_keeps_the_same_identity(
    live_state, embed_calls, monkeypatch
) -> None:
    live_state(A)
    monkeypatch.setattr(
        dedup_mod.analysis_store,
        "search_topics",
        lambda embedding, *, embedder, k, threshold: [  # noqa: ARG005
            {"id": 7, "topic_summary": "older", "distance": 0.1}
        ],
    )
    monkeypatch.setattr(
        dedup_mod,
        "_ask_judge",
        lambda summary, candidates: _Verdict(True, 7),  # noqa: ARG005
    )

    outcome = dedup_mod.run("a summary")

    assert outcome.status == "duplicate"
    assert outcome.matched_topic_id == 7
    assert outcome.embedder == "omlx:embed-A"


def test_embedder_failure_stores_no_provenance(live_state, monkeypatch) -> None:
    """A failed embed must leave behind neither a vector nor an identity."""
    live_state(A)

    def boom():
        raise RuntimeError("embedder request failed (http://x)")

    monkeypatch.setattr(dedup_mod, "get_embedder", boom)

    outcome = dedup_mod.run("a summary")

    assert outcome.status == "novel"
    assert outcome.embedding is None
    assert outcome.embedder is None


def test_unselected_embedder_turns_dedup_off_without_failing(
    live_state, monkeypatch
) -> None:
    """Nobody has chosen one yet: the item still flows, dedup just does nothing."""
    live_state({})
    searched: list[str] = []
    monkeypatch.setattr(
        dedup_mod.analysis_store,
        "search_topics",
        lambda *a, **kw: searched.append("searched") or [],  # noqa: ARG005
    )

    outcome = dedup_mod.run("a summary")

    assert outcome.status == "novel"
    assert outcome.embedding is None
    assert outcome.embedder is None
    # No vector means nothing to search, so the table is never touched.
    assert searched == []


class _Verdict:
    def __init__(self, is_duplicate: bool, matched_topic_id: int | None):
        self.is_duplicate = is_duplicate
        self.matched_topic_id = matched_topic_id
