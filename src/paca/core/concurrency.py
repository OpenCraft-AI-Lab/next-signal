"""Per-provider concurrency limiting for LLM calls.

Why per-provider rather than per-profile or global:

- **Local OMLX**: single GPU/MLX process. Concurrent inferences share the same
  pool of memory and cycles — N parallel runs roughly N× memory and shared
  speed. Mac Studio running Qwen3.6-35B-A3B-4bit hits a sweet spot at 1-2
  concurrent; 3+ degrades or OOMs. Strict limit needed.
- **Cloud APIs** (Claude / OpenAI / Gemini): account-level RPM/TPM far above
  what we'd realistically run. Limiting here just adds latency. Let the cloud
  rate-limit us with 429 and let agno's retry handle it.

The semaphore registry lives at the model layer — every model produced by
``paca.core.models.get_model()`` is wrapped so all call paths (single agent
run, Team member, Workflow Step, @tool wrapping, AgentOS endpoint) automatically
go through it.

Routes that bypass the registry (e.g. browser-use's own OpenAI client inside
``paca/tools/browser.py``) are NOT limited — they need their own integration.
"""

from __future__ import annotations

import asyncio
import threading
from typing import ClassVar

# Default unlimited (effectively) — used when a provider has no explicit limit.
UNLIMITED = 999


class ProviderConcurrency:
    """Process-wide registry of per-provider semaphores. Class-level state.

    Configure once at startup via ``configure(limits)``; from then on, callers
    use ``acquire_async(provider)`` or ``acquire_sync(provider)`` as a context
    manager.
    """

    _limits: ClassVar[dict[str, int]] = {}
    _async_sems: ClassVar[dict[str, asyncio.Semaphore]] = {}
    _sync_sems: ClassVar[dict[str, threading.Semaphore]] = {}
    _sync_lock: ClassVar[threading.Lock] = threading.Lock()
    _async_lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def configure(cls, limits: dict[str, int]) -> None:
        """Set per-provider limits. Call once at startup.

        Reconfiguring after semaphores are in use **replaces** them — any
        thread already holding one of the old semaphores will release it
        into a no-longer-referenced object, which is harmless but means the
        intended behavior is "configure once". Tests use ``reset()``.
        """
        cls._limits = dict(limits)
        # Pre-create sync semaphores eagerly. Async ones lazy (need running loop).
        cls._sync_sems = {
            provider: threading.Semaphore(max(1, n))
            for provider, n in limits.items()
        }
        cls._async_sems = {}

    @classmethod
    def limits(cls) -> dict[str, int]:
        return dict(cls._limits)

    @classmethod
    def limit_for(cls, provider: str) -> int:
        return cls._limits.get(provider, UNLIMITED)

    @classmethod
    def acquire_sync(cls, provider: str) -> threading.Semaphore:
        """Return a sync semaphore for ``provider``. Use as a context manager.

        Auto-creates one if missing (uses default UNLIMITED).
        """
        # Guard against two threads racing to create the same provider's
        # semaphore — without the lock the loser's reference is replaced
        # while the winner still holds the old object, producing an "orphan"
        # semaphore whose releases don't increase the live one's slot count.
        if provider not in cls._sync_sems:
            with cls._sync_lock:
                if provider not in cls._sync_sems:
                    cls._sync_sems[provider] = threading.Semaphore(
                        cls.limit_for(provider)
                    )
        return cls._sync_sems[provider]

    @classmethod
    def acquire_async(cls, provider: str) -> asyncio.Semaphore:
        """Return an async semaphore for ``provider``. Use ``async with``.

        Lazily created on first call from within a running loop.
        """
        # asyncio.Semaphore must be created in (or bound to) the active loop.
        # Two threads racing to create would each get their own — guard with lock.
        if provider not in cls._async_sems:
            with cls._async_lock:
                if provider not in cls._async_sems:
                    cls._async_sems[provider] = asyncio.Semaphore(
                        cls.limit_for(provider)
                    )
        return cls._async_sems[provider]

    @classmethod
    def reset(cls) -> None:
        """Clear all state. Tests use this to start clean."""
        cls._limits = {}
        cls._async_sems = {}
        cls._sync_sems = {}
