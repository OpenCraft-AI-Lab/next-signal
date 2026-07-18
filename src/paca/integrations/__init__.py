"""Shared provider integrations — the generic cloud-API adapter pool.

These adapters are not owned by any vertical module; any module may use them.
Vertical-specific adapters live under that module's ``integrations/`` package.

Each module in this package is independent: failure to register one (e.g. due
to a missing optional dep) must not break the others. Modules expose a
``register(registry)`` function called from the central tool registry.
"""

from __future__ import annotations

import importlib

from paca.core.logging import get_logger

log = get_logger(__name__)

# Order doesn't matter — registration is independent per module.
# Empty in next-signal: the shared cloud-API adapters here (tavily / exa /
# firecrawl / notion / github / slack / news / weather / google_calendar /
# gmail) were only consumed by the personal-assistant/Discord front door,
# which isn't part of this repo's scope. Add a module here if a future
# domain needs one of these adapters as a generic (non-vertical) tool.
_MODULES: list[str] = []


def register_all(registry) -> None:
    for name in _MODULES:
        try:
            mod = importlib.import_module(f"paca.integrations.{name}")
            mod.register(registry)
        except Exception as e:  # noqa: BLE001 — one bad integration must not kill the rest
            log.warning("integration_register_failed", integration=name, error=str(e))
