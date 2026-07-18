from __future__ import annotations

from paca.agents import loader
from paca.core.config import AgentConfig


def test_build_db_free_agent_does_not_touch_db(monkeypatch) -> None:
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.name = kwargs["name"]

    monkeypatch.setattr(loader, "Agent", FakeAgent)
    monkeypatch.setattr(loader, "get_model", lambda name: f"model:{name}")
    monkeypatch.setattr(loader, "resolve_tools", lambda names: [])
    monkeypatch.setattr(
        loader,
        "get_db",
        lambda: (_ for _ in ()).throw(AssertionError("db should not be built")),
    )

    agent = loader.build_from_config(
        AgentConfig(
            name="knowledge_artifact_editor",
            model_profile="local",
            instructions="Return JSON only.",
            markdown=False,
            add_history_to_context=False,
            extra={"db": False, "shared_context": False},
        )
    )

    assert agent.name == "knowledge_artifact_editor"
    assert "db" not in captured
