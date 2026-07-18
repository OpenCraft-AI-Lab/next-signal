"""Tests for the per-provider concurrency limiter.

Two layers:
  1. ProviderConcurrency itself — basic semaphore registry behavior
  2. Model wrapping — verify the wrapper actually serializes calls
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from paca.core import models as models_mod
from paca.core.concurrency import UNLIMITED, ProviderConcurrency


@pytest.fixture(autouse=True)
def _reset_state():
    ProviderConcurrency.reset()
    yield
    ProviderConcurrency.reset()


# ---------------------------------------------------------------------------
# Layer 1: registry behavior
# ---------------------------------------------------------------------------


def test_unconfigured_provider_returns_unlimited() -> None:
    assert ProviderConcurrency.limit_for("anything") == UNLIMITED


def test_configure_sets_limits() -> None:
    ProviderConcurrency.configure({"omlx": 2, "claude": 16})
    assert ProviderConcurrency.limit_for("omlx") == 2
    assert ProviderConcurrency.limit_for("claude") == 16
    assert ProviderConcurrency.limit_for("openai") == UNLIMITED  # not set


def test_sync_semaphore_serializes_concurrent_calls() -> None:
    ProviderConcurrency.configure({"omlx": 1})
    barrier = threading.Barrier(2)
    results: list[float] = []

    def task(idx: int) -> None:
        barrier.wait()
        with ProviderConcurrency.acquire_sync("omlx"):
            results.append(time.monotonic())
            time.sleep(0.05)

    t1 = threading.Thread(target=task, args=(0,))
    t2 = threading.Thread(target=task, args=(1,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Two threads with a limit of 1 → at least 50ms apart.
    assert len(results) == 2
    assert abs(results[1] - results[0]) >= 0.04


@pytest.mark.asyncio
async def test_async_semaphore_serializes_concurrent_calls() -> None:
    ProviderConcurrency.configure({"omlx": 1})
    enter_times: list[float] = []

    async def task() -> None:
        async with ProviderConcurrency.acquire_async("omlx"):
            enter_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.05)

    await asyncio.gather(task(), task(), task())
    assert len(enter_times) == 3
    # Each must enter at least ~50ms after the previous (limit=1, sleep=50ms).
    deltas = [enter_times[i] - enter_times[i - 1] for i in range(1, 3)]
    for d in deltas:
        assert d >= 0.04


def test_higher_limit_allows_concurrency() -> None:
    """With limit=4 and only 3 callers, all should enter immediately."""
    ProviderConcurrency.configure({"claude": 4})
    barrier = threading.Barrier(3)
    enter_times: list[float] = []
    lock = threading.Lock()

    def task() -> None:
        barrier.wait()
        with ProviderConcurrency.acquire_sync("claude"):
            with lock:
                enter_times.append(time.monotonic())
            time.sleep(0.03)

    threads = [threading.Thread(target=task) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 3 entered within a tiny window (limit=4 covers 3).
    spread = max(enter_times) - min(enter_times)
    assert spread < 0.02


# ---------------------------------------------------------------------------
# Layer 2: model wrapper integration
# ---------------------------------------------------------------------------


class _FakeModel:
    """Stand-in for an agno Model — has the four entry-point methods."""

    def __init__(self) -> None:
        self.response_calls = 0
        self.aresponse_calls = 0
        self.stream_calls = 0
        self.astream_calls = 0

    def response(self, *args, **kwargs):
        self.response_calls += 1
        return f"sync-response-{self.response_calls}"

    async def aresponse(self, *args, **kwargs):
        self.aresponse_calls += 1
        return f"async-response-{self.aresponse_calls}"

    def response_stream(self, *args, **kwargs):
        self.stream_calls += 1
        for i in range(3):
            yield f"chunk-{i}"

    async def aresponse_stream(self, *args, **kwargs):
        self.astream_calls += 1
        for i in range(3):
            yield f"chunk-{i}"


def test_wrapper_preserves_response_value() -> None:
    ProviderConcurrency.configure({"omlx": 1})
    m = _FakeModel()
    wrapped = models_mod._wrap_with_concurrency(m, "omlx")
    assert wrapped.response() == "sync-response-1"
    assert wrapped.response() == "sync-response-2"


def test_wrapper_preserves_stream_iteration() -> None:
    ProviderConcurrency.configure({"omlx": 1})
    m = _FakeModel()
    wrapped = models_mod._wrap_with_concurrency(m, "omlx")
    chunks = list(wrapped.response_stream())
    assert chunks == ["chunk-0", "chunk-1", "chunk-2"]


@pytest.mark.asyncio
async def test_wrapper_aresponse_serializes() -> None:
    """With limit=1, two parallel wrapped.aresponse() calls must run sequentially."""
    ProviderConcurrency.configure({"omlx": 1})

    enter_times: list[float] = []

    class _SlowModel(_FakeModel):
        async def aresponse(self, *args, **kwargs):  # type: ignore[override]
            enter_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.04)
            return await super().aresponse(*args, **kwargs)

    m = _SlowModel()
    wrapped = models_mod._wrap_with_concurrency(m, "omlx")

    await asyncio.gather(wrapped.aresponse(), wrapped.aresponse(), wrapped.aresponse())
    assert m.aresponse_calls == 3
    # Limit=1 + each call sleeps 40ms → entries at least 40ms apart.
    assert len(enter_times) == 3
    deltas = [enter_times[i] - enter_times[i - 1] for i in range(1, 3)]
    for d in deltas:
        assert d >= 0.03


def test_wrapper_doesnt_double_call_underlying() -> None:
    ProviderConcurrency.configure({"omlx": 2})
    m = _FakeModel()
    wrapped = models_mod._wrap_with_concurrency(m, "omlx")
    wrapped.response()
    assert m.response_calls == 1
