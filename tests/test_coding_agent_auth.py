"""Allowlisted provider-authentication broker contracts."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import threading
import time

import pytest
from typer.testing import CliRunner

from next_signal.integrations.coding_agents.auth import (
    auth_argv,
    check_auth_status,
    extract_login_urls,
    logout,
    run_login_session,
)
from next_signal.interfaces.cli import app

cli_runner = CliRunner()


def _write_auth_cli(path: Path, provider: str) -> Path:
    # See test_coding_agent_runner._write_fixture: Windows cannot exec a shebang
    # script, so fixture-backed tests skip rather than fail there. The login
    # tests additionally need a PTY, which is POSIX-only for the same reason
    # `auth.py` imports `pty` lazily.
    if sys.platform == "win32":
        pytest.skip("POSIX-only: execs a #!/usr/bin/env python3 fixture")
    marker = path.with_suffix(".logged-in")
    source = f"""#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import time

marker = Path({str(marker)!r})
args = sys.argv[1:]

if args in (["login", "status"], ["auth", "status", "--json"]):
    logged_in = marker.exists()
    if {provider!r} == "claude":
        print(json.dumps({{"loggedIn": logged_in, "authMethod": "claude.ai" if logged_in else "none"}}))
        raise SystemExit(0)
    print("Logged in using ChatGPT" if logged_in else "Not logged in")
    raise SystemExit(0 if logged_in else 1)

if args in (["logout"], ["auth", "logout"]):
    marker.unlink(missing_ok=True)
    print("Logged out")
    raise SystemExit(0)

if args == ["login", "--device-auth"]:
    print("Open https://auth.openai.com/codex/device", flush=True)
    marker.write_text("ok")
    raise SystemExit(0)

if args == ["auth", "login", "--claudeai"]:
    print("Open https://claude.com/cai/oauth/authorize?code=fake", flush=True)
    code = sys.stdin.readline().strip()
    if code != "browser-code":
        print("bad code", flush=True)
        raise SystemExit(9)
    marker.write_text("ok")
    print("Authorized", flush=True)
    raise SystemExit(0)

if args == ["auth", "login", "slow"]:
    time.sleep(30)

print("unexpected argv: " + repr(args), flush=True)
raise SystemExit(8)
"""
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.mark.parametrize(
    ("provider", "operation", "expected"),
    [
        ("codex", "login", ["/bin/codex", "login", "--device-auth"]),
        ("codex", "status", ["/bin/codex", "login", "status"]),
        ("codex", "logout", ["/bin/codex", "logout"]),
        ("claude", "login", ["/bin/claude", "auth", "login", "--claudeai"]),
        ("claude", "status", ["/bin/claude", "auth", "status", "--json"]),
        ("claude", "logout", ["/bin/claude", "auth", "logout"]),
    ],
)
def test_auth_argv_is_fixed(provider: str, operation: str, expected: list[str]) -> None:
    assert auth_argv(provider, operation, f"/bin/{provider}") == expected


def test_auth_argv_rejects_unsupported_values() -> None:
    with pytest.raises(ValueError, match="provider"):
        auth_argv("other", "login", "/tmp/other")
    with pytest.raises(ValueError, match="operation"):
        auth_argv("codex", "shell", "/bin/codex")


def test_login_url_allowlist_is_provider_specific() -> None:
    text = (
        "https://auth.openai.com/codex/device "
        "https://claude.com/cai/oauth/authorize "
        "http://auth.openai.com/insecure https://openai.com.evil.example/phish"
    )

    assert extract_login_urls("codex", text) == ["https://auth.openai.com/codex/device"]
    assert extract_login_urls("claude", text) == ["https://claude.com/cai/oauth/authorize"]


def test_status_reports_only_sanitized_connection_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_auth_cli(tmp_path / "claude", "claude")
    monkeypatch.setenv("CLAUDE_BIN", str(executable))

    before = check_auth_status("claude")
    executable.with_suffix(".logged-in").write_text("ok", encoding="utf-8")
    after = check_auth_status("claude")

    assert before == {
        "provider": "claude",
        "available": True,
        "connected": False,
        "message": "Not connected",
    }
    assert after == {
        "provider": "claude",
        "available": True,
        "connected": True,
        "message": "Connected",
    }


def test_logout_uses_provider_command_and_removes_saved_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_auth_cli(tmp_path / "codex", "codex")
    executable.with_suffix(".logged-in").write_text("ok", encoding="utf-8")
    monkeypatch.setenv("CODEX_BIN", str(executable))

    result = logout("codex")

    assert result == {
        "provider": "codex",
        "ok": True,
        "connected": False,
        "error": None,
    }


def test_claude_login_relays_one_line_without_echoing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_auth_cli(tmp_path / "claude", "claude")
    monkeypatch.setenv("CLAUDE_BIN", str(executable))
    events: list[dict[str, object]] = []

    result = run_login_session(
        "claude",
        emit=events.append,
        input_stream=io.StringIO("browser-code\nsecond-line-is-ignored\n"),
        timeout_seconds=2,
    )

    assert result["ok"] is True
    assert result["connected"] is True
    assert [event["url"] for event in events if event["type"] == "url"] == [
        "https://claude.com/cai/oauth/authorize?code=fake"
    ]
    transcript = "".join(str(event["text"]) for event in events if event["type"] == "output")
    assert "Authorized" in transcript
    assert "browser-code" not in transcript
    assert "second-line" not in transcript


def test_login_timeout_terminates_provider_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_auth_cli(tmp_path / "claude", "claude")
    monkeypatch.setenv("CLAUDE_BIN", str(executable))
    monkeypatch.setattr(
        "next_signal.integrations.coding_agents.auth.auth_argv",
        lambda provider, operation, executable: [executable, "auth", "login", "slow"],
    )
    started = time.monotonic()

    result = run_login_session(
        "claude",
        emit=lambda _: None,
        input_stream=io.StringIO(""),
        timeout_seconds=0.1,
    )

    assert time.monotonic() - started < 2
    assert result["ok"] is False
    assert result["timed_out"] is True


def test_login_cancellation_terminates_provider_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_auth_cli(tmp_path / "claude", "claude")
    monkeypatch.setenv("CLAUDE_BIN", str(executable))
    monkeypatch.setattr(
        "next_signal.integrations.coding_agents.auth.auth_argv",
        lambda provider, operation, executable: [executable, "auth", "login", "slow"],
    )
    cancelled = threading.Event()
    timer = threading.Timer(0.1, cancelled.set)
    timer.start()
    try:
        result = run_login_session(
            "claude",
            emit=lambda _: None,
            input_stream=io.StringIO(""),
            timeout_seconds=2,
            cancelled=cancelled,
        )
    finally:
        timer.cancel()

    assert result["ok"] is False
    assert result["cancelled"] is True


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-only: run_login_session needs a PTY, and the fixture is a shebang script",
)
def test_login_output_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable = tmp_path / "codex"
    executable.write_text(
        "#!/usr/bin/env python3\nprint('x' * 10000, flush=True)\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("CODEX_BIN", str(executable))

    result = run_login_session(
        "codex",
        emit=lambda _: None,
        input_stream=io.StringIO(""),
        timeout_seconds=2,
        max_output_chars=128,
    )

    assert result["ok"] is False
    assert "output limit" in str(result["error"])


def test_auth_status_cli_emits_one_json_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_auth_cli(tmp_path / "codex", "codex")
    executable.with_suffix(".logged-in").write_text("ok", encoding="utf-8")
    monkeypatch.setenv("CODEX_BIN", str(executable))

    result = cli_runner.invoke(app, ["coding-agent", "auth-status", "codex"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "provider": "codex",
        "available": True,
        "connected": True,
        "message": "Connected",
    }


def test_auth_login_cli_is_jsonl_and_rejects_unknown_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _write_auth_cli(tmp_path / "claude", "claude")
    monkeypatch.setenv("CLAUDE_BIN", str(executable))

    result = cli_runner.invoke(
        app,
        ["coding-agent", "auth-login", "claude"],
        input="browser-code\n",
    )
    rejected = cli_runner.invoke(app, ["coding-agent", "auth-login", "other"])

    assert result.exit_code == 0, result.output
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert lines[0]["type"] == "started"
    assert lines[-1]["type"] == "result"
    assert lines[-1]["connected"] is True
    assert rejected.exit_code == 2
    assert "valid providers" in rejected.output
