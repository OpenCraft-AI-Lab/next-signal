"""Smoke tests for the integration helpers — no network calls."""

from __future__ import annotations

import os

import pytest

from paca.integrations import _helpers as h


def test_env_missing_raises_with_hint() -> None:
    os.environ.pop("PACA_NEVER_SET_THIS", None)
    with pytest.raises(RuntimeError, match="PACA_NEVER_SET_THIS"):
        h.env("PACA_NEVER_SET_THIS", hint="from the test")


def test_env_returns_value(monkeypatch) -> None:
    monkeypatch.setenv("PACA_TEST_VAR", "  yes  ")
    assert h.env("PACA_TEST_VAR") == "yes"


def test_truncate_short_passthrough() -> None:
    assert h.truncate("hi", 100) == "hi"


def test_truncate_long_marks_count() -> None:
    out = h.truncate("x" * 1000, 200)
    assert "truncated" in out
    assert len(out) <= 250


def test_to_jsonable_handles_nested() -> None:
    class Foo:
        pass

    assert h.to_jsonable({"a": [1, 2, Foo()]})["a"][2].startswith("<")


def test_rate_limit_sleeps_outside_global_lock(monkeypatch) -> None:
    h._LAST_CALL_BY_BUCKET.clear()
    h._LAST_CALL_BY_BUCKET["bucket"] = 100.0
    monkeypatch.setattr(h.time, "monotonic", lambda: 100.5)

    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        assert not h._RATE_LIMIT_LOCK.locked()
        slept.append(seconds)

    monkeypatch.setattr(h.time, "sleep", fake_sleep)

    h.rate_limit("bucket", min_interval=1.0)

    assert slept == [0.5]
