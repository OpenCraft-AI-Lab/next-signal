"""Live coding-agent preference-file contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from next_signal.core.coding_agent_preferences import load_coding_agent_preferences


def test_absent_preferences_require_both_cli_selections(tmp_path: Path) -> None:
    preferences = load_coding_agent_preferences(tmp_path / "missing.json")

    assert preferences.codex is None
    assert preferences.claude is None


def test_valid_coding_agent_preferences_load_exact_provider_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / "coding-agents.json"
    path.write_text(
        json.dumps(
            {
                "codex": {
                    "model": "gpt-5.6-sol",
                    "model_reasoning_effort": "high",
                    "service_tier": "fast",
                },
                "claude": {
                    "model": "opus[1m]",
                    "effort": "xhigh",
                },
                "updated_at": "2026-08-09T12:00:00Z",
                "updated_by": "dashboard",
            }
        ),
        encoding="utf-8",
    )

    preferences = load_coding_agent_preferences(path)

    assert preferences.codex.model == "gpt-5.6-sol"
    assert preferences.codex.model_reasoning_effort == "high"
    assert preferences.codex.service_tier == "fast"
    assert preferences.claude.model == "opus[1m]"
    assert preferences.claude.effort == "xhigh"


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        '{"codex":{"model_reasoning_effort":"ultra"}}',
        '{"codex":{"service_tier":"priority"}}',
        '{"codex":{"model":"bad model"}}',
        '{"codex":{"unknown":true}}',
        '{"codex":{"model":"gpt-5.6-sol"}}',
        '{"claude":{"effort":"ultra"}}',
        '{"claude":{"model":"bad model"}}',
        '{"claude":{"unknown":true}}',
    ],
)
def test_malformed_coding_agent_preferences_fail_loud(body: str, tmp_path: Path) -> None:
    path = tmp_path / "coding-agents.json"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(RuntimeError, match="coding-agents.json"):
        load_coding_agent_preferences(path)
