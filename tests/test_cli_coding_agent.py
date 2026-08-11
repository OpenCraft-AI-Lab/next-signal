"""CLI surface tests for optional coding-agent workers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from next_signal.core import config
from next_signal.core.coding_agent_preferences import (
    CodexPreferences,
    CodingAgentPreferences,
)
from next_signal.integrations.coding_agents import runner as coding_agent_runner
from next_signal.interfaces.cli import app

runner = CliRunner()


def _write_config(path: Path, root: Path, *, unknown: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    extra = "unknown: true\n" if unknown else ""
    (path / "coding_agents.yaml").write_text(
        f"""allowed_roots: [{str(root)!r}]
default_profile: review
providers:
  codex:
    enabled: true
    timeout_seconds: 2
    max_event_bytes: 4096
    max_stderr_chars: 1024
    terminate_grace_seconds: 0.1
    inherit_env: []
    inherit_user_config: true
  claude:
    enabled: true
    timeout_seconds: 2
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
{extra}""",
        encoding="utf-8",
    )


def _write_cli(path: Path, provider: str, *, fail: bool = False) -> Path:
    source = f"""#!/usr/bin/env python3
import json
import sys

if "--version" in sys.argv:
    print("fake-{provider} 1.0")
    raise SystemExit(0)
prompt = sys.stdin.read()
if {fail!r}:
    print("failed", file=sys.stderr)
    raise SystemExit(9)
if {provider!r} == "codex":
    print(json.dumps({{"type": "thread.started", "thread_id": "cli-codex"}}))
    print(json.dumps({{"type": "item.completed", "item": {{"type": "agent_message", "text": json.dumps({{"argv": sys.argv[1:], "prompt": prompt}})}}}}))
    print(json.dumps({{"type": "turn.completed", "usage": {{"output_tokens": 1}}}}))
else:
    print(json.dumps({{"type": "system", "subtype": "init", "session_id": "cli-claude"}}))
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "session_id": "cli-claude", "result": prompt, "usage": {{}}}}))
"""
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


def _setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    codex_fail: bool = False,
) -> None:
    configs = tmp_path / "configs"
    _write_config(configs, tmp_path)
    monkeypatch.setattr(config, "CONFIGS_DIR", configs)
    monkeypatch.setenv("CODEX_BIN", str(_write_cli(tmp_path / "codex", "codex", fail=codex_fail)))
    monkeypatch.setenv("CLAUDE_BIN", str(_write_cli(tmp_path / "claude", "claude")))
    monkeypatch.setattr(
        coding_agent_runner,
        "load_coding_agent_preferences",
        lambda: CodingAgentPreferences(
            codex=CodexPreferences(
                model="gpt-5.6-sol",
                model_reasoning_effort="high",
                service_tier="default",
            )
        ),
    )


def test_coding_agent_doctor_checks_versions_without_model_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)

    result = runner.invoke(app, ["coding-agent", "doctor"])

    assert result.exit_code == 0, result.output
    assert "✓ codex: fake-codex 1.0" in result.output
    assert "✓ claude: fake-claude 1.0" in result.output


def test_coding_agent_doctor_reports_missing_enabled_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("CODEX_BIN", str(tmp_path / "missing"))

    result = runner.invoke(app, ["coding-agent", "doctor"])

    assert result.exit_code == 1
    assert "✗ codex:" in result.output
    assert "CODEX_BIN" in result.output


def test_coding_agent_doctor_rejects_invalid_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs = tmp_path / "configs"
    _write_config(configs, tmp_path, unknown=True)
    monkeypatch.setattr(config, "CONFIGS_DIR", configs)

    result = runner.invoke(app, ["coding-agent", "doctor"])

    assert result.exit_code == 1
    assert "coding-agent config" in result.output
    assert "unknown" in result.output


def test_coding_agent_run_defaults_to_review_and_prints_one_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["coding-agent", "run", "codex", "review me", "--cwd", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["type"] == "result"
    assert payload["ok"] is True
    record = json.loads(payload["text"])
    assert "read-only" in record["argv"]
    assert record["prompt"] == "review me"


def test_coding_agent_run_edit_profile_and_progress_are_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "coding-agent",
            "run",
            "codex",
            "edit me",
            "--cwd",
            str(tmp_path),
            "--profile",
            "edit",
            "--progress",
        ],
    )

    assert result.exit_code == 0, result.output
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert all(line["type"] == "event" for line in lines[:-1])
    assert lines[-1]["type"] == "result"
    record = json.loads(lines[-1]["text"])
    assert "workspace-write" in record["argv"]


@pytest.mark.parametrize(
    ("provider", "extra", "message"),
    [
        ("other", [], "valid providers"),
        ("codex", ["--profile", "absent"], "configured profiles"),
    ],
)
def test_coding_agent_run_rejects_unknown_provider_or_profile_before_spawn(
    provider: str,
    extra: list[str],
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["coding-agent", "run", provider, "x", "--cwd", str(tmp_path), *extra],
    )

    assert result.exit_code == 2
    assert message in result.output


def test_coding_agent_run_provider_failure_exits_nonzero_with_json_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch, codex_fail=True)

    result = runner.invoke(
        app,
        ["coding-agent", "run", "codex", "x", "--cwd", str(tmp_path)],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["returncode"] == 9
