from __future__ import annotations

from contextvars import copy_context
import threading

import pytest
from pydantic import BaseModel

from next_signal.agents import stage
from next_signal.core.coding_agent_preferences import (
    CodingAgentPreferences,
    CodexPreferences,
)
from next_signal.core.engine_preferences import EngineNotSelected, configured_engine_defaults
from next_signal.integrations.coding_agents.types import CodingAgentResult


class _Output(BaseModel):
    value: int


def _preferences(primary="codex_cli", fallback="claude_cli"):
    return configured_engine_defaults().model_copy(
        update={"primary": primary, "fallback": fallback}
    )


def _codex_prefs(model: str, effort: str = "high") -> CodingAgentPreferences:
    return CodingAgentPreferences(
        codex=CodexPreferences(
            model=model, model_reasoning_effort=effort, service_tier="fast"
        )
    )


def test_nothing_selected_raises_its_own_type() -> None:
    """Distinguishable from a failure, mirroring `EmbedderNotSelected` — no
    degraded mode exists for a production stage job, so this blocks it."""
    with pytest.raises(EngineNotSelected, match="No engine has been selected"):
        with stage.stage_job(configured_engine_defaults()):
            pass


def test_primary_failure_before_first_response_pins_fallback(monkeypatch) -> None:
    calls = []

    def invoke(engine, *args):
        calls.append(engine)
        if engine == "codex_cli":
            raise stage.StageInvocationError("offline")
        return '{"value": 7}'

    monkeypatch.setattr(stage, "_invoke_engine", invoke)
    with stage.stage_job(_preferences()) as state:
        first = stage.run_stage("radar_tier1_filter", "one", _Output)
        second = stage.run_stage("radar_tier1_filter", "two", _Output)

    assert first.value == second.value == 7
    assert calls == ["codex_cli", "claude_cli", "claude_cli"]
    assert state.selected == "claude_cli"
    assert state.locked is True


def test_later_failure_never_switches_provider(monkeypatch) -> None:
    calls = []

    def invoke(engine, *args):
        calls.append(engine)
        if len(calls) == 1:
            return "ok"
        raise stage.StageInvocationError("later failure")

    monkeypatch.setattr(stage, "_invoke_engine", invoke)
    with stage.stage_job(_preferences()):
        assert stage.run_stage("knowledge_frontmatter", "one") == "ok"
        with pytest.raises(stage.StageInvocationError, match="later failure"):
            stage.run_stage("knowledge_frontmatter", "two")

    assert calls == ["codex_cli", "codex_cli"]


def test_schema_failure_repairs_on_same_locked_provider(monkeypatch) -> None:
    calls = []
    responses = iter(['{"value":"bad"}', '{"value":9}'])

    def invoke(engine, preferences, cfg, agent_input, output_schema, language):
        calls.append((engine, agent_input))
        return next(responses)

    monkeypatch.setattr(stage, "_invoke_engine", invoke)
    with stage.stage_job(_preferences()) as state:
        result = stage.run_stage("radar_tier1_filter", "original", _Output)

    assert result.value == 9
    assert [engine for engine, _ in calls] == ["codex_cli", "codex_cli"]
    assert "previous reply was rejected" in calls[1][1]
    assert state.locked is True


def test_copied_thread_context_shares_job_affinity(monkeypatch) -> None:
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def invoke(engine, *args):
        calls.append(engine)
        entered.set()
        release.wait(timeout=1)
        return "ok"

    monkeypatch.setattr(stage, "_invoke_engine", invoke)
    with stage.stage_job(_preferences()) as state:
        context = copy_context()
        thread = threading.Thread(
            target=context.run,
            args=(stage.run_stage, "knowledge_frontmatter", "thread"),
        )
        thread.start()
        assert entered.wait(timeout=1)
        release.set()
        thread.join(timeout=1)

    assert calls == ["codex_cli"]
    assert state.locked is True


def test_cli_prompt_preserves_instructions_language_input_and_schema() -> None:
    cfg = stage.load_agent("radar_tier1_filter")
    schema = _Output.model_json_schema()

    prompt = stage._cli_prompt(cfg, "SOURCE INPUT", language=None, json_schema=schema)

    assert "You triage a BATCH of feed items" in prompt
    assert "{{OUTPUT_LANGUAGE}}" not in prompt
    assert "SOURCE INPUT" in prompt
    assert "Do not inspect repository files" in prompt
    assert '"value"' in prompt


def test_plain_stage_rejects_empty_success(monkeypatch) -> None:
    monkeypatch.setattr(stage, "_invoke_engine", lambda *args: "  ")

    with stage.stage_job(_preferences()):
        with pytest.raises(RuntimeError, match="empty text"):
            stage.run_stage("knowledge_frontmatter", "input")


def test_cli_stage_uses_ephemeral_empty_workspace_and_stage_profile(
    tmp_path, monkeypatch
) -> None:
    captured = {}

    async def fake_run(request, *, config, preferences):
        captured["request"] = request
        captured["allowed_roots"] = config.resolved_allowed_roots()
        captured["exists_during_run"] = request.cwd.is_dir()
        captured["contents_during_run"] = list(request.cwd.iterdir())
        return CodingAgentResult(ok=True, provider=request.provider, text="ok")

    monkeypatch.setattr(stage, "AGENT_TMP_DIR", tmp_path)
    monkeypatch.setattr(stage, "run_coding_agent", fake_run)

    cfg = stage.load_agent("knowledge_frontmatter")
    result = stage._invoke_cli(
        "codex_cli", CodingAgentPreferences(), cfg, "input", None, None
    )

    request = captured["request"]
    assert result == "ok"
    assert request.profile == "stage"
    assert request.cwd.parent == tmp_path / "coding-agent-stage"
    assert captured["allowed_roots"] == (request.cwd.resolve(),)
    assert captured["exists_during_run"] is True
    assert captured["contents_during_run"] == []
    assert request.cwd.exists() is False


def test_job_provenance_records_actual_cli_model_settings(monkeypatch) -> None:
    state = stage.StageJobState(
        preferences=_preferences(),
        selected="codex_cli",
        coding_agents=_codex_prefs("gpt-5.6-sol", "high"),
        locked=True,
    )
    # Provenance must describe the job, not the file as it stands now: an edit
    # landing mid-job would otherwise be attributed to work it never touched.
    monkeypatch.setattr(
        stage,
        "load_coding_agent_preferences",
        lambda: _codex_prefs("edited-after-the-job-started", "low"),
    )

    provenance = stage.stage_job_provenance(state)

    assert provenance["selected"] == "codex_cli"
    assert provenance["coding_agent"] == {
        "model": "gpt-5.6-sol",
        "model_reasoning_effort": "high",
        "service_tier": "fast",
    }


def test_saved_job_state_cannot_be_rebound_inside_another_job() -> None:
    first = stage.StageJobState(
        preferences=_preferences(),
        selected="codex_cli",
        coding_agents=CodingAgentPreferences(),
        locked=False,
    )
    second = stage.StageJobState(
        preferences=_preferences(),
        selected="codex_cli",
        coding_agents=CodingAgentPreferences(),
        locked=False,
    )

    with stage.stage_job(state=first):
        with pytest.raises(RuntimeError, match="different stage job"):
            with stage.stage_job(state=second):
                pass


def test_cli_model_settings_are_frozen_for_the_whole_job(tmp_path, monkeypatch) -> None:
    """An edit landing mid-job must not reach stages that job has left to run.

    A radar job runs for tens of minutes over a batch whose scores are compared
    against each other, so half a batch scored by a different model is a wrong
    ranking rather than a cosmetic inconsistency.
    """
    models: list[str] = []

    async def fake_run(request, *, config, preferences):
        models.append(preferences.codex.model)
        return CodingAgentResult(ok=True, provider=request.provider, text="ok")

    on_disk = [_codex_prefs("model-at-job-start")]
    monkeypatch.setattr(stage, "AGENT_TMP_DIR", tmp_path)
    monkeypatch.setattr(stage, "run_coding_agent", fake_run)
    monkeypatch.setattr(stage, "load_coding_agent_preferences", lambda: on_disk[0])

    with stage.stage_job(_preferences(primary="codex_cli", fallback="none")) as state:
        assert stage.run_stage("knowledge_frontmatter", "one") == "ok"
        on_disk[0] = _codex_prefs("model-the-operator-switched-to")  # settings page
        assert stage.run_stage("knowledge_frontmatter", "two") == "ok"

    assert models == ["model-at-job-start", "model-at-job-start"]
    assert stage.stage_job_provenance(state)["coding_agent"]["model"] == (
        "model-at-job-start"
    )


def test_cli_stage_runs_from_inside_a_live_event_loop(tmp_path, monkeypatch) -> None:
    """AgentOS reaches production stages through `Workflow.arun`.

    agno runs a sync step executor inline on the loop thread, so a bare
    `asyncio.run` raises there — and the affinity layer reads that as "this
    engine is unavailable" and quietly falls back, which looks like a missing
    CLI rather than a wrong call.
    """
    import asyncio

    async def fake_run(request, *, config, preferences):
        return CodingAgentResult(ok=True, provider=request.provider, text="ran")

    monkeypatch.setattr(stage, "AGENT_TMP_DIR", tmp_path)
    monkeypatch.setattr(stage, "run_coding_agent", fake_run)

    async def drive() -> object:
        return stage._invoke_cli(
            "codex_cli", CodingAgentPreferences(), stage.load_agent(
                "knowledge_frontmatter"
            ), "input", None, None
        )

    assert asyncio.run(drive()) == "ran"
