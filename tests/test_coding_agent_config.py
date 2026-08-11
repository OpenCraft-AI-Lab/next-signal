"""Configuration contracts for the external coding-agent CLI bridge."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from next_signal.core import config


def _write_config(path: Path, body: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "coding_agents.yaml").write_text(body, encoding="utf-8")


_VALID = """
allowed_roots: ['.']
default_profile: review
providers:
  codex:
    enabled: true
    timeout_seconds: 30
    max_event_bytes: 4096
    max_stderr_chars: 1024
    terminate_grace_seconds: 0.1
    inherit_env: []
    inherit_user_config: true
  claude:
    enabled: true
    timeout_seconds: 30
    max_event_bytes: 4096
    max_stderr_chars: 1024
    terminate_grace_seconds: 0.1
    inherit_env: []
    bare: false
profiles:
  review:
    codex_sandbox: read-only
    claude_permission_mode: dontAsk
    claude_allowed_tools: [Read, Glob, Grep]
  edit:
    codex_sandbox: workspace-write
    claude_permission_mode: dontAsk
    claude_allowed_tools: [Read, Edit]
"""


def test_coding_agents_config_loads_and_resolves_default_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs = tmp_path / "configs"
    _write_config(configs, _VALID)
    monkeypatch.setattr(config, "CONFIGS_DIR", configs)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    cfg = config.load_coding_agents()

    assert cfg.default_profile == "review"
    assert cfg.profile().codex_sandbox == "read-only"
    assert cfg.resolved_allowed_roots() == (tmp_path.resolve(),)


def test_coding_agents_config_rejects_unknown_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs = tmp_path / "configs"
    _write_config(configs, _VALID + "unknown_setting: true\n")
    monkeypatch.setattr(config, "CONFIGS_DIR", configs)

    with pytest.raises(ValidationError, match="unknown_setting"):
        config.load_coding_agents()


def test_coding_agents_config_rejects_missing_default_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs = tmp_path / "configs"
    _write_config(configs, _VALID.replace("default_profile: review", "default_profile: absent"))
    monkeypatch.setattr(config, "CONFIGS_DIR", configs)

    with pytest.raises(ValidationError, match="default_profile.*absent"):
        config.load_coding_agents()


def test_coding_agents_config_rejects_unsafe_provider_modes() -> None:
    data = {
        "allowed_roots": ["."],
        "default_profile": "unsafe",
        "providers": {
            "codex": {},
            "claude": {},
        },
        "profiles": {
            "unsafe": {
                "codex_sandbox": "danger-full-access",
                "claude_permission_mode": "bypassPermissions",
                "claude_allowed_tools": [],
            }
        },
    }

    with pytest.raises(ValidationError):
        config.CodingAgentsConfig.model_validate(data)
