"""Central tool registry for agent-facing capabilities."""

from __future__ import annotations

from typing import Callable

from paca.core.logging import get_logger

log = get_logger(__name__)

_REGISTRY: dict[str, Callable] = {}
_REGISTERED = False


class _RegistryFacade:
    """Adapter so integration modules can call ``registry.register(name, fn)``."""

    @staticmethod
    def register(name: str, fn: Callable) -> None:
        register(name, fn)


def register(name: str, fn: Callable) -> None:
    if name in _REGISTRY:
        raise ValueError(f"tool {name!r} already registered")
    _REGISTRY[name] = fn


def resolve_tools(names: list[str]) -> list[Callable]:
    _ensure_registered()
    missing = [n for n in names if n not in _REGISTRY]
    if missing:
        raise KeyError(f"unknown tools: {missing}; available: {sorted(_REGISTRY)}")
    return [_REGISTRY[n] for n in names]


def available() -> list[str]:
    _ensure_registered()
    return sorted(_REGISTRY)


def _ensure_registered() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    _REGISTERED = True
    _register_all()


def _register_all() -> None:
    """Wire up all tool sources."""
    for mod_name, names in _IN_TREE_TOOLS.items():
        try:
            mod = __import__(f"paca.tools.{mod_name}", fromlist=names)
        except ImportError as e:
            log.warning("in_tree_module_import_failed", module=mod_name, error=str(e))
            continue
        for n in names:
            register(n, getattr(mod, n))  # AttributeError propagates — bug in our code

    for package in _TOOL_PACKAGES:
        try:
            mod = __import__(f"paca.tools.{package}", fromlist=["register"])
            mod.register(_RegistryFacade())
        except Exception as e:  # noqa: BLE001
            log.warning("tool_package_register_failed", package=package, error=str(e))

    from paca.orchestrator.workflow_tools import register_workflow_tools
    register_workflow_tools(_RegistryFacade())

    from paca.integrations import register_all
    register_all(_RegistryFacade())


_IN_TREE_TOOLS: dict[str, list[str]] = {
    "gbrain": ["gbrain_search", "gbrain_get", "gbrain_query", "gbrain_ingest"],
}

_TOOL_PACKAGES = ["knowledge"]
