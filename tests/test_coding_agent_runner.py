"""Real subprocess tests for the bounded coding-agent runner."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

import pytest

from next_signal.core.coding_agent_preferences import (
    ClaudePreferences,
    CodexPreferences,
    CodingAgentPreferences,
)
from next_signal.core.config import CodingAgentsConfig
from next_signal.integrations.coding_agents.runner import run_coding_agent, validate_workspace
from next_signal.integrations.coding_agents.types import (
    CodingAgentEvent,
    CodingAgentRunRequest,
)


def _config(
    root: Path,
    *,
    timeout: float = 2,
    max_event_bytes: int = 4096,
    inherit_env: list[str] | None = None,
) -> CodingAgentsConfig:
    provider = {
        "enabled": True,
        "timeout_seconds": timeout,
        "max_event_bytes": max_event_bytes,
        "max_stderr_chars": 80,
        "terminate_grace_seconds": 0.2,
        "inherit_env": inherit_env or [],
    }
    return CodingAgentsConfig.model_validate(
        {
            "allowed_roots": [str(root)],
            "default_profile": "review",
            "providers": {
                "codex": {**provider, "inherit_user_config": True},
                "claude": {**provider, "bare": False},
            },
            "profiles": {
                "review": {
                    "codex_sandbox": "read-only",
                    "claude_permission_mode": "dontAsk",
                    "claude_allowed_tools": ["Read", "Glob", "Grep"],
                },
                "edit": {
                    "codex_sandbox": "workspace-write",
                    "claude_permission_mode": "dontAsk",
                    "claude_allowed_tools": ["Read", "Edit"],
                },
            },
        }
    )


def _codex_preferences() -> CodingAgentPreferences:
    return CodingAgentPreferences(
        codex=CodexPreferences(
            model="gpt-5.6-sol",
            model_reasoning_effort="high",
            service_tier="default",
        ),
        claude=ClaudePreferences(model="sonnet", effort="high"),
    )


def _write_fixture(path: Path, provider: str, behavior: str = "success") -> Path:
    # These are real-subprocess tests: the fixture is a shebang script the runner
    # execs. Windows cannot exec one (WinError 193), so every test that builds a
    # fixture skips there rather than failing. Guarding the helper keeps future
    # tests covered without another decorator.
    if sys.platform == "win32":
        pytest.skip("POSIX-only: execs a #!/usr/bin/env python3 fixture")
    source = f"""#!/usr/bin/env python3
import json
import os
import sys
import time

if "--version" in sys.argv:
    print("fake-{provider} 1.0")
    raise SystemExit(0)

behavior = {behavior!r}
prompt = sys.stdin.read()
record = json.dumps({{
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "prompt": prompt,
    "visible": os.environ.get("VISIBLE_ENV"),
    "secret": os.environ.get("PARENT_SECRET"),
}})

if behavior == "hang":
    pid_file = os.environ.get("PID_FILE")
    if pid_file:
        open(pid_file, "w", encoding="utf-8").write(str(os.getpid()))
    time.sleep(30)
elif behavior == "malformed":
    print("not json")
elif behavior == "oversized":
    print(json.dumps({{"type": "event", "data": "x" * 10000}}))
elif behavior == "missing-terminal":
    print(json.dumps({{"type": "thread.started", "thread_id": "only-start"}}))
elif behavior == "nonzero":
    print("diagnostic-" + "x" * 200, file=sys.stderr)
    raise SystemExit(7)
elif {provider!r} == "codex":
    print(json.dumps({{"type": "thread.started", "thread_id": "codex-session"}}))
    print(json.dumps({{"type": "item.completed", "item": {{"type": "agent_message", "text": record}}}}))
    print(json.dumps({{"type": "turn.completed", "usage": {{"output_tokens": 3}}}}))
else:
    print(json.dumps({{"type": "system", "subtype": "init", "session_id": "claude-session"}}))
    print(json.dumps({{
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "session_id": "claude-session",
        "result": record,
        "usage": {{"output_tokens": 4}},
    }}))
"""
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["codex", "claude"])
async def test_success_run_records_real_argv_cwd_stdin_and_environment(
    provider: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executable = _write_fixture(tmp_path / provider, provider)
    monkeypatch.setenv(f"{provider.upper()}_BIN", str(executable))
    monkeypatch.setenv("VISIBLE_ENV", "visible")
    monkeypatch.setenv("PARENT_SECRET", "must-not-leak")
    events: list[CodingAgentEvent] = []
    prompt = 'literal $(touch /tmp/nope) `echo nope` "quoted"'

    result = await run_coding_agent(
        CodingAgentRunRequest(
            provider=provider,
            prompt=prompt,
            cwd=workspace,
        ),
        config=_config(tmp_path, inherit_env=["VISIBLE_ENV"]),
        preferences=_codex_preferences(),
        on_event=events.append,
    )

    assert result.ok is True, result
    record = json.loads(result.text)
    assert record["cwd"] == str(workspace)
    assert record["prompt"] == prompt
    assert record["visible"] == "visible"
    assert record["secret"] is None
    assert result.session_id == f"{provider}-session"
    assert result.usage["output_tokens"] in {3, 4}
    assert events and all(event.provider == provider for event in events)
    if provider == "codex":
        assert record["argv"][-1] == "-"
        assert "--ephemeral" in record["argv"]
        assert "--skip-git-repo-check" in record["argv"]
        assert "read-only" in record["argv"]
    else:
        assert "--no-session-persistence" in record["argv"]
        assert "bypassPermissions" not in record["argv"]


@pytest.mark.asyncio
async def test_claude_run_applies_runtime_model_and_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_fixture(tmp_path / "claude", "claude")
    monkeypatch.setenv("CLAUDE_BIN", str(executable))

    result = await run_coding_agent(
        CodingAgentRunRequest(provider="claude", prompt="review", cwd=tmp_path),
        config=_config(tmp_path),
        preferences=CodingAgentPreferences(claude=ClaudePreferences(model="sonnet", effort="high")),
    )

    assert result.ok is True, result
    argv = json.loads(result.text)["argv"]
    assert argv[argv.index("--model") + 1] == "sonnet"
    assert argv[argv.index("--effort") + 1] == "high"


@pytest.mark.asyncio
async def test_codex_run_rejects_unconfigured_preferences_before_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_fixture(tmp_path / "codex", "codex")
    monkeypatch.setenv("CODEX_BIN", str(executable))

    result = await run_coding_agent(
        CodingAgentRunRequest(provider="codex", prompt="review", cwd=tmp_path),
        config=_config(tmp_path),
        preferences=CodingAgentPreferences(),
    )

    assert result.ok is False
    assert result.returncode is None
    assert "must be explicitly configured" in (result.error or "")


def test_workspace_validation_accepts_child_and_rejects_outside(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    child = root / "child"
    child.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    cfg = _config(root)

    assert validate_workspace(child, cfg) == child
    with pytest.raises(RuntimeError, match="outside configured allowed_roots"):
        validate_workspace(outside, cfg)


def test_workspace_validation_rejects_dotdot_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    link.symlink_to(outside, target_is_directory=True)
    cfg = _config(root)

    with pytest.raises(RuntimeError, match="outside configured allowed_roots"):
        validate_workspace(root / ".." / "outside", cfg)
    with pytest.raises(RuntimeError, match="outside configured allowed_roots"):
        validate_workspace(link, cfg)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("behavior", "error"),
    [
        ("malformed", "malformed JSONL"),
        ("oversized", "exceeds 1024 bytes"),
        ("missing-terminal", "terminal event missing"),
    ],
)
async def test_protocol_failures_are_explicit(
    behavior: str,
    error: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = _write_fixture(tmp_path / "codex", "codex", behavior)
    monkeypatch.setenv("CODEX_BIN", str(executable))

    result = await run_coding_agent(
        CodingAgentRunRequest(provider="codex", prompt="x", cwd=tmp_path),
        config=_config(tmp_path, max_event_bytes=1024),
        preferences=_codex_preferences(),
    )

    assert result.ok is False
    assert error in (result.error or "")


@pytest.mark.asyncio
async def test_nonzero_exit_keeps_bounded_stderr_and_never_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_fixture(tmp_path / "codex", "codex", "nonzero")
    claude_marker = tmp_path / "claude-was-called"
    claude = tmp_path / "claude"
    claude.write_text(f"#!/bin/sh\ntouch {claude_marker}\n", encoding="utf-8")
    claude.chmod(0o755)
    monkeypatch.setenv("CODEX_BIN", str(executable))
    monkeypatch.setenv("CLAUDE_BIN", str(claude))

    result = await run_coding_agent(
        CodingAgentRunRequest(provider="codex", prompt="x", cwd=tmp_path),
        config=_config(tmp_path),
        preferences=_codex_preferences(),
    )

    assert result.ok is False
    assert result.returncode == 7
    assert len(result.stderr) == 80
    assert not claude_marker.exists()


@pytest.mark.asyncio
async def test_timeout_returns_failure_and_terminates_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_fixture(tmp_path / "codex", "codex", "hang")
    monkeypatch.setenv("CODEX_BIN", str(executable))

    result = await run_coding_agent(
        CodingAgentRunRequest(provider="codex", prompt="x", cwd=tmp_path),
        config=_config(tmp_path, timeout=0.1),
        preferences=_codex_preferences(),
    )

    assert result.ok is False
    assert result.timed_out is True
    assert "timed out" in (result.error or "")
    assert result.returncode is not None


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="process-group assertion is POSIX-specific")
async def test_cancellation_terminates_provider_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_fixture(tmp_path / "codex", "codex", "hang")
    pid_file = tmp_path / "pid"
    monkeypatch.setenv("CODEX_BIN", str(executable))
    monkeypatch.setenv("PID_FILE", str(pid_file))
    cfg = _config(tmp_path, timeout=10, inherit_env=["PID_FILE"])
    task = asyncio.create_task(
        run_coding_agent(
            CodingAgentRunRequest(provider="codex", prompt="x", cwd=tmp_path),
            config=cfg,
            preferences=_codex_preferences(),
        )
    )
    for _ in range(100):
        if pid_file.exists():
            break
        await asyncio.sleep(0.01)
    assert pid_file.exists()
    pid = int(pid_file.read_text(encoding="utf-8"))

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
