"""Tests for centralized runnable loading.

Invariants: one bad YAML never blocks the rest, zero agents refuses to start,
``expose.agent_os: false`` thin shells stay out of AgentOS, and factory refs
are validated loudly.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from paca.orchestrator import runnable_loader as rl


def test_one_bad_agent_does_not_block_others(monkeypatch) -> None:
    monkeypatch.setattr(rl, "list_agents", lambda: ["good", "bad", "good2"])
    monkeypatch.setattr(rl, "load_agent", lambda name: SimpleNamespace(enabled=True))

    def build(name: str) -> str:
        if name == "bad":
            raise RuntimeError("broken yaml")
        return f"agent:{name}"

    monkeypatch.setattr(rl, "build_from_name", build)

    assert rl.load_agents() == ["agent:good", "agent:good2"]


def test_disabled_agent_is_skipped(monkeypatch) -> None:
    monkeypatch.setattr(rl, "list_agents", lambda: ["off", "on"])
    monkeypatch.setattr(
        rl, "load_agent", lambda name: SimpleNamespace(enabled=(name == "on"))
    )
    monkeypatch.setattr(rl, "build_from_name", lambda name: f"agent:{name}")

    assert rl.load_agents() == ["agent:on"]


def test_zero_agents_refuses_to_start(monkeypatch) -> None:
    monkeypatch.setattr(rl, "list_agents", lambda: ["only"])
    monkeypatch.setattr(rl, "load_agent", lambda name: SimpleNamespace(enabled=True))
    monkeypatch.setattr(
        rl,
        "build_from_name",
        lambda name: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(RuntimeError, match="no agents loaded"):
        rl.load_agents()


def test_workflow_not_exposed_to_agent_os_is_skipped(monkeypatch) -> None:
    cfgs = {
        "shown": SimpleNamespace(
            enabled=True, expose=SimpleNamespace(agent_os=True), factory="x:y"
        ),
        "shell": SimpleNamespace(
            enabled=True, expose=SimpleNamespace(agent_os=False), factory="x:y"
        ),
    }
    monkeypatch.setattr(rl, "list_workflows", lambda: list(cfgs))
    monkeypatch.setattr(rl, "load_workflow", lambda name: cfgs[name])
    monkeypatch.setattr(rl, "build_workflow_from_config", lambda cfg: f"wf:{cfg.factory}")

    assert rl.load_workflows() == ["wf:x:y"]


def test_load_factory_resolves_module_colon_callable() -> None:
    import json

    assert rl.load_factory("json:loads") is json.loads


def test_load_factory_rejects_bad_ref() -> None:
    with pytest.raises(RuntimeError, match="factory must be"):
        rl.load_factory("no-colon-here")


def test_load_factory_rejects_non_callable() -> None:
    with pytest.raises(RuntimeError, match="not callable"):
        rl.load_factory("paca.core.paths:PROJECT_ROOT")
