"""Provider-specific argv and JSONL parsing contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from next_signal.core.coding_agent_preferences import (
    ClaudePreferences,
    CodexPreferences,
)
from next_signal.core.config import (
    ClaudeCliConfig,
    CodexCliConfig,
    CodingAgentProfile,
)
from next_signal.integrations.coding_agents import claude, codex
from next_signal.integrations.coding_agents.discovery import resolve_executable
from next_signal.integrations.coding_agents.errors import CodingAgentProtocolError
from next_signal.integrations.coding_agents.types import ProviderParseState


def _profile(*, edit: bool = False) -> CodingAgentProfile:
    return CodingAgentProfile(
        codex_sandbox="workspace-write" if edit else "read-only",
        claude_permission_mode="dontAsk",
        claude_allowed_tools=["Read", "Edit"] if edit else ["Read", "Glob", "Grep"],
    )


def _isolated_profile() -> CodingAgentProfile:
    return CodingAgentProfile(
        codex_sandbox="read-only",
        claude_permission_mode="dontAsk",
        claude_allowed_tools=[],
        tool_access="none",
    )


def test_resolve_executable_prefers_provider_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "my-codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("CODEX_BIN", str(executable))

    assert resolve_executable("codex") == str(executable)


def test_resolve_executable_missing_has_remediation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)

    with pytest.raises(RuntimeError, match="CLAUDE_BIN"):
        resolve_executable("claude")


def test_codex_builds_safe_one_shot_argv() -> None:
    argv = codex.build_argv(
        "/bin/codex",
        _profile(),
        CodexCliConfig(),
        CodexPreferences(
            model="gpt-5.6-sol",
            model_reasoning_effort="high",
            service_tier="default",
        ),
    )
    assert argv == [
        "/bin/codex",
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--model",
        "gpt-5.6-sol",
        "--config",
        'model_reasoning_effort="high"',
        "--config",
        'service_tier="default"',
        "-",
    ]
    assert "danger-full-access" not in argv
    assert "resume" not in argv


def test_codex_edit_and_ignore_user_config_flags() -> None:
    argv = codex.build_argv(
        "/bin/codex",
        _profile(edit=True),
        CodexCliConfig(inherit_user_config=False),
        CodexPreferences(
            model="gpt-5.6-sol",
            model_reasoning_effort="high",
            service_tier="default",
        ),
    )
    assert "workspace-write" in argv
    assert "--ignore-user-config" in argv


def test_codex_isolated_stage_disables_tools_and_instructions() -> None:
    argv = codex.build_argv(
        "/bin/codex",
        _isolated_profile(),
        CodexCliConfig(inherit_user_config=True),
        CodexPreferences(
            model="gpt-5.6-sol",
            model_reasoning_effort="high",
            service_tier="default",
        ),
    )

    assert "--ignore-user-config" in argv
    assert "--ignore-rules" in argv
    disabled = [argv[index + 1] for index, value in enumerate(argv) if value == "--disable"]
    assert {"shell_tool", "unified_exec", "apps", "browser_use"} <= set(disabled)


def test_codex_rejects_missing_explicit_preferences() -> None:
    with pytest.raises(ValueError, match="must be explicitly configured"):
        codex.build_argv("/bin/codex", _profile(), CodexCliConfig())


def test_codex_builds_explicit_model_effort_and_fast_tier_argv() -> None:
    argv = codex.build_argv(
        "/bin/codex",
        _profile(),
        CodexCliConfig(),
        CodexPreferences(
            model="gpt-5.6-sol",
            model_reasoning_effort="high",
            service_tier="fast",
        ),
    )

    assert argv[-1] == "-"
    assert argv[argv.index("--model") + 1] == "gpt-5.6-sol"
    assert 'model_reasoning_effort="high"' in argv
    assert 'service_tier="fast"' in argv
    assert "features.fast_mode=true" in argv


def test_codex_parser_extracts_thread_text_usage_and_success() -> None:
    state = ProviderParseState()
    codex.consume_event({"type": "thread.started", "thread_id": "thr-1"}, state)
    codex.consume_event(
        {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
        state,
    )
    codex.consume_event({"type": "turn.completed", "usage": {"output_tokens": 7}}, state)

    assert state.session_id == "thr-1"
    assert state.text == "done"
    assert state.usage == {"output_tokens": 7}
    assert state.terminal_seen is True
    assert state.terminal_ok is True


def test_claude_builds_safe_one_shot_argv() -> None:
    argv = claude.build_argv(
        "/bin/claude",
        _profile(),
        ClaudeCliConfig(),
        ClaudePreferences(model="sonnet", effort="high"),
    )
    assert argv[:2] == ["/bin/claude", "-p"]
    assert "stream-json" in argv
    assert "--include-partial-messages" in argv
    assert "--no-session-persistence" in argv
    assert "dontAsk" in argv
    assert "Read,Glob,Grep" in argv
    assert "bypassPermissions" not in argv
    assert "--resume" not in argv


def test_claude_bare_and_edit_flags() -> None:
    argv = claude.build_argv(
        "/bin/claude",
        _profile(edit=True),
        ClaudeCliConfig(bare=True),
        ClaudePreferences(model="sonnet", effort="high"),
    )
    assert argv[1] == "--bare"
    assert "Read,Edit" in argv


def test_claude_isolated_stage_disables_tools_and_customizations() -> None:
    argv = claude.build_argv(
        "/bin/claude",
        _isolated_profile(),
        ClaudeCliConfig(),
        ClaudePreferences(model="sonnet", effort="high"),
    )

    assert "--safe-mode" in argv
    assert "--disable-slash-commands" in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert "--allowedTools" not in argv


def test_claude_builds_explicit_model_and_effort_argv() -> None:
    argv = claude.build_argv(
        "/bin/claude",
        _profile(),
        ClaudeCliConfig(),
        ClaudePreferences(model="opus", effort="xhigh"),
    )

    assert argv[argv.index("--model") + 1] == "opus"
    assert argv[argv.index("--effort") + 1] == "xhigh"


def test_claude_builds_json_schema_argv() -> None:
    schema = {"type": "object", "properties": {"keep": {"type": "boolean"}}}
    argv = claude.build_argv(
        "/bin/claude",
        _profile(),
        ClaudeCliConfig(),
        ClaudePreferences(model="sonnet", effort="high"),
        json_schema=schema,
    )

    assert json.loads(argv[argv.index("--json-schema") + 1]) == schema


def test_codex_does_not_emit_unsupported_json_schema_flag() -> None:
    argv = codex.build_argv(
        "/bin/codex",
        _profile(),
        CodexCliConfig(),
        CodexPreferences(
            model="gpt-5.6-sol",
            model_reasoning_effort="high",
            service_tier="default",
        ),
        json_schema={"type": "object"},
    )

    assert "--json-schema" not in argv


def test_claude_rejects_missing_explicit_preferences() -> None:
    with pytest.raises(ValueError, match="must be explicitly configured"):
        claude.build_argv("/bin/claude", _profile(), ClaudeCliConfig())


def test_claude_parser_extracts_session_result_usage_and_cost() -> None:
    state = ProviderParseState()
    claude.consume_event({"type": "system", "subtype": "init", "session_id": "sess-1"}, state)
    claude.consume_event(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "session_id": "sess-1",
            "result": "finished",
            "usage": {"output_tokens": 9},
            "total_cost_usd": 0.02,
        },
        state,
    )

    assert state.session_id == "sess-1"
    assert state.text == "finished"
    assert state.usage == {"output_tokens": 9, "total_cost_usd": 0.02}
    assert state.terminal_seen is True
    assert state.terminal_ok is True


@pytest.mark.parametrize("adapter", [codex, claude])
def test_provider_parser_rejects_event_without_type(adapter) -> None:
    with pytest.raises(CodingAgentProtocolError, match="type"):
        adapter.consume_event({"message": "bad"}, ProviderParseState())
