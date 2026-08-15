"""Bounded, allowlisted authentication for Codex and Claude Code CLIs.

Provider credentials remain owned by the provider CLI.  This module only runs
the provider's fixed status/login/logout commands and normalizes enough state
for the local Dashboard; it never reads or copies credential files.
"""

from __future__ import annotations

import codecs
from collections.abc import Callable
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import threading
import time
from typing import IO, Any, Literal, TypedDict, cast
from urllib.parse import urlsplit

# `pty` and `termios` are POSIX-only and are imported where they are used, not
# here. Provider login genuinely needs a PTY, so that path stays POSIX-only —
# but importing this module must not. `auth_argv`, `check_auth_status`,
# `logout`, and `extract_login_urls` are all portable, and a module-level
# import made the whole test suite uncollectable on Windows rather than
# failing only the one path that cannot work there.

from next_signal.integrations.coding_agents.discovery import resolve_executable
from next_signal.integrations.coding_agents.types import ProviderName

AuthOperation = Literal["login", "status", "logout"]

DEFAULT_LOGIN_TIMEOUT_SECONDS = 10 * 60.0
DEFAULT_MAX_OUTPUT_CHARS = 32_768
MAX_INPUT_CHARS = 4_096
STATUS_TIMEOUT_SECONDS = 10.0
TERMINATE_GRACE_SECONDS = 0.75

_ANSI_RE = re.compile(r"(?:\x1b\][^\x07]*(?:\x07|\x1b\\))|(?:\x1b\[[0-?]*[ -/]*[@-~])")
_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_ALLOWED_LOGIN_DOMAINS: dict[ProviderName, tuple[str, ...]] = {
    "codex": ("openai.com", "chatgpt.com"),
    "claude": ("claude.com", "claude.ai", "anthropic.com"),
}
_AUTH_ENV_NAMES = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "CODEX_HOME",
    "CLAUDE_CONFIG_DIR",
)


class AuthStatus(TypedDict):
    provider: ProviderName
    available: bool
    connected: bool
    message: str


class AuthSessionResult(TypedDict):
    type: Literal["result"]
    provider: ProviderName
    ok: bool
    connected: bool
    returncode: int | None
    timed_out: bool
    cancelled: bool
    error: str | None


def _provider(value: str) -> ProviderName:
    if value not in {"codex", "claude"}:
        raise ValueError(f"unknown coding-agent provider {value!r}; valid providers: claude, codex")
    return cast(ProviderName, value)


def auth_argv(provider: str, operation: str, executable: str) -> list[str]:
    """Map a provider and operation to one fixed argv; no caller-supplied tail."""
    selected = _provider(provider)
    if operation not in {"login", "status", "logout"}:
        raise ValueError(f"unknown coding-agent auth operation {operation!r}")

    commands: dict[ProviderName, dict[AuthOperation, list[str]]] = {
        "codex": {
            "login": ["login", "--device-auth"],
            "status": ["login", "status"],
            "logout": ["logout"],
        },
        "claude": {
            "login": ["auth", "login", "--claudeai"],
            "status": ["auth", "status", "--json"],
            "logout": ["auth", "logout"],
        },
    }
    return [executable, *commands[selected][cast(AuthOperation, operation)]]


def _auth_environment() -> dict[str, str]:
    env = {name: os.environ[name] for name in _AUTH_ENV_NAMES if os.environ.get(name)}
    env.setdefault("PATH", os.defpath)
    env.setdefault("HOME", str(Path.home()))
    env.setdefault("LANG", "C.UTF-8")
    env["TERM"] = "xterm-256color"
    # Claude's image version is immutable; upgrades happen through a rebuild.
    env["DISABLE_AUTOUPDATER"] = "1"
    return env


def _safe_message(error: Exception) -> str:
    return str(error).replace("\n", " ")[:500]


def check_auth_status(provider: str) -> AuthStatus:
    """Run a provider's status command and return no identity or credential data."""
    selected = _provider(provider)
    try:
        executable = resolve_executable(selected)
        completed = subprocess.run(
            auth_argv(selected, "status", executable),
            check=False,
            capture_output=True,
            text=True,
            timeout=STATUS_TIMEOUT_SECONDS,
            env=_auth_environment(),
        )
    except Exception as exc:  # noqa: BLE001 - normalized for operator status
        return {
            "provider": selected,
            "available": False,
            "connected": False,
            "message": _safe_message(exc),
        }

    output = (completed.stdout or completed.stderr)[:8_192]
    connected = False
    if selected == "claude":
        try:
            payload = json.loads(output)
            connected = payload.get("loggedIn") is True if isinstance(payload, dict) else False
        except json.JSONDecodeError:
            connected = completed.returncode == 0 and "not logged" not in output.lower()
    else:
        connected = completed.returncode == 0 and "not logged" not in output.lower()

    return {
        "provider": selected,
        "available": True,
        "connected": connected,
        "message": "Connected" if connected else "Not connected",
    }


def logout(provider: str) -> dict[str, Any]:
    """Run only the selected provider's fixed logout command."""
    selected = _provider(provider)
    try:
        executable = resolve_executable(selected)
        completed = subprocess.run(
            auth_argv(selected, "logout", executable),
            check=False,
            capture_output=True,
            timeout=STATUS_TIMEOUT_SECONDS,
            env=_auth_environment(),
        )
    except Exception as exc:  # noqa: BLE001 - normalized for the local UI
        return {
            "provider": selected,
            "ok": False,
            "connected": False,
            "error": _safe_message(exc),
        }

    status = check_auth_status(selected)
    ok = completed.returncode == 0 and not status["connected"]
    return {
        "provider": selected,
        "ok": ok,
        "connected": status["connected"],
        "error": None if ok else f"{selected} logout exited with code {completed.returncode}",
    }


def _strip_terminal_controls(text: str) -> str:
    cleaned = _ANSI_RE.sub("", text)
    return "".join(char for char in cleaned if char in "\n\r\t" or ord(char) >= 32)


def _hostname_allowed(provider: ProviderName, hostname: str | None) -> bool:
    if not hostname:
        return False
    normalized = hostname.rstrip(".").lower()
    return any(
        normalized == domain or normalized.endswith(f".{domain}")
        for domain in _ALLOWED_LOGIN_DOMAINS[provider]
    )


def extract_login_urls(provider: str, text: str) -> list[str]:
    """Return unique HTTPS URLs on the selected provider's explicit allowlist."""
    selected = _provider(provider)
    urls: list[str] = []
    for match in _URL_RE.findall(_strip_terminal_controls(text)):
        candidate = match.rstrip(".,;:!?)]}>")
        parsed = urlsplit(candidate)
        if parsed.scheme != "https" or not _hostname_allowed(selected, parsed.hostname):
            continue
        if candidate not in urls:
            urls.append(candidate)
    return urls


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        process.terminate()
    try:
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()
    try:
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass


def _configure_no_echo(slave_fd: int) -> None:
    import termios

    attrs = termios.tcgetattr(slave_fd)
    attrs[3] &= ~termios.ECHO
    termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)


def run_login_session(
    provider: str,
    *,
    emit: Callable[[dict[str, Any]], None],
    input_stream: IO[str] = sys.stdin,
    timeout_seconds: float = DEFAULT_LOGIN_TIMEOUT_SECONDS,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    cancelled: threading.Event | None = None,
) -> AuthSessionResult:
    """Run one provider login in a PTY and emit bounded normalized JSON objects.

    POSIX-only: raises ``ImportError`` on platforms without ``pty``.
    """
    import pty

    selected = _provider(provider)
    cancel_event = cancelled or threading.Event()
    process: subprocess.Popen[bytes] | None = None
    master_fd: int | None = None
    slave_fd: int | None = None
    timed_out = False
    was_cancelled = False
    error: str | None = None
    returncode: int | None = None
    output_chars = 0
    transcript = ""
    emitted_urls: set[str] = set()
    input_error: list[str] = []
    previous_sigterm: Any = None

    def request_cancel(_signum: int, _frame: Any) -> None:
        cancel_event.set()

    try:
        executable = resolve_executable(selected)
        argv = auth_argv(selected, "login", executable)
        master_fd, slave_fd = pty.openpty()
        _configure_no_echo(slave_fd)
        process = subprocess.Popen(
            argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=_auth_environment(),
            close_fds=True,
            start_new_session=True,
        )
        os.close(slave_fd)
        slave_fd = None
        emit({"type": "started", "provider": selected})

        if threading.current_thread() is threading.main_thread():
            previous_sigterm = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, request_cancel)

        def relay_one_input_line() -> None:
            line = input_stream.readline(MAX_INPUT_CHARS + 2)
            if not line:
                return
            value = line.rstrip("\r\n")
            if len(value) > MAX_INPUT_CHARS:
                input_error.append(f"authorization input exceeds {MAX_INPUT_CHARS} characters")
                cancel_event.set()
                return
            try:
                if master_fd is not None:
                    os.write(master_fd, f"{value}\n".encode())
            except OSError:
                return

        threading.Thread(target=relay_one_input_line, daemon=True).start()

        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        started = time.monotonic()
        while True:
            if cancel_event.is_set():
                was_cancelled = True
                error = input_error[0] if input_error else "authentication cancelled"
                break
            if time.monotonic() - started >= timeout_seconds:
                timed_out = True
                error = f"authentication timed out after {timeout_seconds:g} seconds"
                break

            ready, _, _ = select.select([master_fd], [], [], 0.05)
            if ready:
                try:
                    data = os.read(master_fd, 4_096)
                except OSError:
                    data = b""
                if data:
                    chunk = _strip_terminal_controls(decoder.decode(data))
                    output_chars += len(chunk)
                    if output_chars > max_output_chars:
                        error = f"authentication output limit exceeded ({max_output_chars} chars)"
                        break
                    if chunk:
                        transcript = (transcript + chunk)[-max_output_chars:]
                        emit({"type": "output", "provider": selected, "text": chunk})
                        for url in extract_login_urls(selected, transcript):
                            if url not in emitted_urls:
                                emitted_urls.add(url)
                                emit({"type": "url", "provider": selected, "url": url})
                    continue

            if process.poll() is not None:
                returncode = process.returncode
                break
    except Exception as exc:  # noqa: BLE001 - normalized for JSONL protocol
        error = _safe_message(exc)
    finally:
        if process is not None:
            if process.poll() is None:
                _terminate_process_group(process)
            returncode = process.returncode
        if master_fd is not None:
            # Clear before closing, not after. The relay thread can still be
            # blocked on stdin, and its `master_fd is not None` check is the
            # only thing between a late authorization code and a descriptor
            # this process has already handed back to the OS to reuse.
            fd, master_fd = master_fd, None
            try:
                os.close(fd)
            except OSError:
                pass
        if slave_fd is not None:
            try:
                os.close(slave_fd)
            except OSError:
                pass
        if previous_sigterm is not None:
            signal.signal(signal.SIGTERM, previous_sigterm)

    status = check_auth_status(selected) if error is None and returncode == 0 else None
    connected = bool(status and status["connected"])
    ok = returncode == 0 and connected and error is None
    if not ok and error is None:
        error = (
            "provider login finished but no saved login was found"
            if returncode == 0
            else f"provider login exited with code {returncode}"
        )
    result: AuthSessionResult = {
        "type": "result",
        "provider": selected,
        "ok": ok,
        "connected": connected,
        "returncode": returncode,
        "timed_out": timed_out,
        "cancelled": was_cancelled,
        "error": error,
    }
    emit(dict(result))
    return result
