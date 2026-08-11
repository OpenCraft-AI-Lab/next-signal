"""Claude Code CLI argv and stream-JSON event adapter."""

from __future__ import annotations

import json
from typing import Any

from next_signal.core.coding_agent_preferences import ClaudePreferences
from next_signal.core.config import ClaudeCliConfig, CodingAgentProfile
from next_signal.integrations.coding_agents.errors import CodingAgentProtocolError
from next_signal.integrations.coding_agents.types import ProviderParseState


def build_argv(
    executable: str,
    profile: CodingAgentProfile,
    settings: ClaudeCliConfig,
    preferences: ClaudePreferences | None = None,
    *,
    json_schema: dict[str, Any] | None = None,
) -> list[str]:
    if preferences is None:
        raise ValueError(
            "Claude model and thinking effort must be explicitly configured "
            "in Dashboard settings"
        )
    selected = preferences
    argv = [executable]
    if settings.bare and profile.tool_access != "none":
        argv.append("--bare")
    if profile.tool_access == "none":
        # ``--safe-mode`` skips CLAUDE.md, hooks, plugins, skills, and MCP;
        # the empty tool set is the provider-enforced filesystem/tool fence.
        argv += ["--safe-mode", "--disable-slash-commands", "--tools", ""]
    argv += [
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--no-session-persistence",
        "--permission-mode",
        profile.claude_permission_mode,
    ]
    argv += ["--model", selected.model, "--effort", selected.effort]
    if json_schema is not None:
        argv += ["--json-schema", json.dumps(json_schema, separators=(",", ":"))]
    if profile.tool_access != "none" and profile.claude_allowed_tools:
        argv += ["--allowedTools", ",".join(profile.claude_allowed_tools)]
    return argv


def consume_event(event: dict[str, Any], state: ProviderParseState) -> None:
    event_type = event.get("type")
    if not isinstance(event_type, str):
        raise CodingAgentProtocolError("claude event is missing string field 'type'")

    session_id = event.get("session_id")
    if isinstance(session_id, str):
        state.session_id = session_id

    if event_type == "assistant":
        text = _assistant_text(event)
        if text:
            state.text = text
        return

    if event_type != "result":
        return

    result_text = event.get("result")
    if isinstance(result_text, str):
        state.text = result_text
    usage = event.get("usage")
    if isinstance(usage, dict):
        state.usage = dict(usage)
    cost = event.get("total_cost_usd")
    if isinstance(cost, int | float):
        state.usage["total_cost_usd"] = cost

    state.terminal_seen = True
    subtype = event.get("subtype")
    state.terminal_ok = event.get("is_error") is not True and subtype not in {
        "error",
        "error_max_turns",
        "error_during_execution",
    }
    if not state.terminal_ok:
        error = event.get("error")
        state.error = error if isinstance(error, str) else state.text or "claude run failed"


def _assistant_text(event: dict[str, Any]) -> str:
    message = event.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    parts = [
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]
    return "".join(parts)
