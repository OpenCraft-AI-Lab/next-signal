from __future__ import annotations

import json

import pytest

from next_signal.core.engine_preferences import (
    EnginePreferences,
    configured_engine_defaults,
    load_engine_preferences,
)


@pytest.fixture
def defaults() -> EnginePreferences:
    return configured_engine_defaults()


def test_configured_defaults_follow_models_yaml(defaults: EnginePreferences) -> None:
    # No engine is chosen on a fresh install — `models.yaml` only prefills the
    # omlx/deepseek panes' own fields, the same way `embedders` prefills Radar
    # Embedding's panes without selecting a provider.
    assert defaults.primary is None
    assert defaults.fallback == "none"
    # The local server's address is the one thing the repo cannot know, so a
    # fresh install reads as unset rather than borrowing an environment value.
    assert defaults.omlx.base_url is None
    assert defaults.omlx.model == "Qwen3.5-122B-A10B-mlx-oQ4"
    assert defaults.omlx.parallel == 2
    assert defaults.deepseek.model == "deepseek-v4-flash"
    assert defaults.deepseek.reasoning == "low"


def test_absent_state_uses_configured_defaults(tmp_path, defaults: EnginePreferences) -> None:
    assert load_engine_preferences(tmp_path / "missing.json", defaults=defaults) == defaults


@pytest.mark.parametrize("engine", ["omlx", "deepseek", "codex_cli", "claude_cli"])
def test_every_engine_can_be_selected(tmp_path, defaults: EnginePreferences, engine: str) -> None:
    path = tmp_path / "engine.json"
    path.write_text(json.dumps({"primary": engine, "fallback": "none"}))

    selected = load_engine_preferences(path, defaults=defaults)

    assert selected.primary == engine
    assert selected.fallback == "none"
    assert selected.omlx == defaults.omlx


def test_partial_nested_settings_merge_with_defaults(
    tmp_path, defaults: EnginePreferences
) -> None:
    path = tmp_path / "engine.json"
    path.write_text(json.dumps({"omlx": {"parallel": 4}}))

    selected = load_engine_preferences(path, defaults=defaults)

    assert selected.omlx.parallel == 4
    assert selected.omlx.model == defaults.omlx.model


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        json.dumps({"primary": "ollama"}),
        json.dumps({"primary": "omlx", "fallback": "omlx"}),
        json.dumps({"temperature": 0.4}),
        json.dumps({"omlx": {"parallel": 3}}),
        json.dumps({"deepseek": {"reasoning": "max"}}),
    ],
)
def test_present_invalid_state_fails_loudly(
    tmp_path, defaults: EnginePreferences, payload: str
) -> None:
    path = tmp_path / "engine.json"
    path.write_text(payload)

    with pytest.raises(RuntimeError, match="invalid engine preferences"):
        load_engine_preferences(path, defaults=defaults)
