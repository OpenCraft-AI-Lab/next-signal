"""Codex CLI argv and JSONL event adapter."""

from __future__ import annotations

from typing import Any

from next_signal.core.coding_agent_preferences import CodexPreferences
from next_signal.core.config import CodingAgentProfile, CodexCliConfig
from next_signal.integrations.coding_agents.errors import CodingAgentProtocolError
from next_signal.integrations.coding_agents.types import ProviderParseState

_ISOLATED_DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    "code_mode_host",
    "apps",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "computer_use",
    "multi_agent",
    "multi_agent_v2",
    "plugins",
    "hooks",
    "workspace_dependencies",
)


def build_argv(
    executable: str,
    profile: CodingAgentProfile,
    settings: CodexCliConfig,
    preferences: CodexPreferences | None = None,
    *,
    json_schema: dict[str, Any] | None = None,
) -> list[str]:
    # The pinned Codex CLI has no stage-level JSON-schema flag. The stage
    # adapter includes this contract in the prompt and validates locally.
    _ = json_schema
    if preferences is None:
        raise ValueError(
            "Codex model, reasoning effort, and speed must be explicitly configured "
            "in Dashboard settings"
        )
    selected = preferences
    argv = [
        executable,
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        profile.codex_sandbox,
    ]
    if profile.tool_access == "none":
        # Stage input can contain prompt injection. Do not load repository or
        # user instructions, and disable every pinned-CLI feature that can
        # reach files, commands, browsers, apps, or delegated agents.
        argv.extend(["--ignore-user-config", "--ignore-rules"])
        for feature in _ISOLATED_DISABLED_FEATURES:
            argv.extend(["--disable", feature])
    elif not settings.inherit_user_config:
        argv.append("--ignore-user-config")
    argv.extend(["--model", selected.model])
    argv.extend(
        [
            "--config",
            f'model_reasoning_effort="{selected.model_reasoning_effort}"',
        ]
    )
    argv.extend(["--config", f'service_tier="{selected.service_tier}"'])
    if selected.service_tier == "fast":
        argv.extend(["--config", "features.fast_mode=true"])
    argv.append("-")
    return argv


def consume_event(event: dict[str, Any], state: ProviderParseState) -> None:
    event_type = event.get("type")
    if not isinstance(event_type, str):
        raise CodingAgentProtocolError("codex event is missing string field 'type'")

    if event_type == "thread.started":
        thread_id = event.get("thread_id")
        if isinstance(thread_id, str):
            state.session_id = thread_id
        return

    if event_type == "item.completed":
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str):
                state.text = text
        return

    if event_type == "turn.completed":
        usage = event.get("usage")
        if isinstance(usage, dict):
            state.usage = usage
        state.terminal_seen = True
        state.terminal_ok = True
        return

    if event_type == "turn.failed":
        state.terminal_seen = True
        state.terminal_ok = False
        state.error = _error_text(event) or "codex turn failed"
        return

    if event_type == "error":
        state.error = _error_text(event) or "codex reported an error"


def _error_text(event: dict[str, Any]) -> str | None:
    for key in ("message", "error"):
        value = event.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            message = value.get("message")
            if isinstance(message, str):
                return message
    return None
