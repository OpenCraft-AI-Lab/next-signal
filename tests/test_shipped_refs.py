"""Every identifier written as a *string* in the shipped tree points at real code.

Imports are checked by the interpreter; string references are not. YAML factory
refs resolve only when a workflow is invoked, and the dashboard's env var names
are a separate hardcoding of the same contract Python holds — both drift
silently. These tests make the drift loud.
"""

from __future__ import annotations

import importlib.util
import re
import tomllib
from pathlib import Path

import pytest

from next_signal.core import config
from next_signal.core.paths import PROJECT_ROOT
from next_signal.orchestrator.runnable_loader import load_factory

# ---------------------------------------------------------------------------
# Workflow YAML refs
# ---------------------------------------------------------------------------

# `extra` keys whose value is a `<module>:<callable>` ref, like `factory`.
_EXTRA_REF_KEYS = ("run_now", "tool_fn")


@pytest.mark.parametrize("name", config.list_workflows())
def test_shipped_workflow_refs_resolve(name: str) -> None:
    cfg = config.load_workflow(name)
    refs = [cfg.factory]
    refs += [str(cfg.extra[k]) for k in _EXTRA_REF_KEYS if cfg.extra.get(k)]
    for ref in refs:
        assert callable(load_factory(ref)), ref


@pytest.mark.parametrize("name", config.list_agents())
def test_shipped_agent_config_loads(name: str) -> None:
    cfg = config.load_agent(name)
    assert cfg.name == name
    # Resolves prompts/agents/<name>.md, so a moved prompt file fails here too.
    assert cfg.resolved_instructions().strip()


def test_parametrized_sweeps_are_not_empty() -> None:
    # A globbing bug would make both sweeps above vacuously pass.
    assert config.list_workflows()
    assert config.list_agents()


# ---------------------------------------------------------------------------
# Entry-point refs — resolved by uvicorn / the console script, never imported
# ---------------------------------------------------------------------------

_UVICORN_TARGET = re.compile(r'uvicorn\.run\(\s*"([^"]+)"')


def test_entry_point_module_refs_exist() -> None:
    cli_src = (PROJECT_ROOT / "src" / "next_signal" / "interfaces" / "cli.py").read_text(
        encoding="utf-8"
    )
    refs = _UVICORN_TARGET.findall(cli_src)
    assert refs, "no uvicorn target found in cli.py — did `serve` move?"

    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    refs += list(pyproject["project"]["scripts"].values())

    for ref in refs:
        module = ref.partition(":")[0]
        # find_spec, not import — os_app builds the whole runtime on import.
        assert importlib.util.find_spec(module) is not None, ref


# ---------------------------------------------------------------------------
# Python <-> dashboard env var contract
# ---------------------------------------------------------------------------

_TS_ENV = re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)")

# Dashboard-only env vars, with no counterpart on the Python side by design.
_TS_ONLY = {
    "NODE_ENV",  # Next.js
    "NEXT_RUNTIME",  # Next.js
    "CHROME_BIN",  # dashboard-only browser launch
    "NEXT_SIGNAL_DATABASE_URL",  # dashboard-only override of DATABASE_URL
}

_TS_SOURCES = ("app", "components", "lib")


def _dashboard_ts_files() -> list[Path]:
    root = PROJECT_ROOT / "dashboard"
    files = [p for p in root.glob("*.ts") if not p.name.endswith(".d.ts")]
    for d in _TS_SOURCES:
        files += [p for p in (root / d).rglob("*.ts*") if ".test." not in p.name]
    return files


def test_dashboard_env_vars_have_a_python_counterpart() -> None:
    ts_vars: set[str] = set()
    for p in _dashboard_ts_files():
        ts_vars |= set(_TS_ENV.findall(p.read_text(encoding="utf-8")))
    assert ts_vars, "scanned no dashboard env reads — did the source dirs move?"

    py = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (PROJECT_ROOT / "src" / "next_signal").rglob("*.py")
    )
    orphans = sorted(v for v in ts_vars - _TS_ONLY if f'"{v}"' not in py)

    assert not orphans, (
        f"dashboard reads env vars the pipeline never does: {orphans}. "
        "Rename both sides together, or add the var to _TS_ONLY."
    )
