"""Bounded subprocess supervision for external coding-agent CLIs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from next_signal.core.coding_agent_preferences import (
    CodingAgentPreferences,
    load_coding_agent_preferences,
)
from next_signal.core.config import (
    CodingAgentProviderConfig,
    CodingAgentsConfig,
    load_coding_agents,
)
from next_signal.core.paths import PROJECT_ROOT
from next_signal.integrations.coding_agents import claude, codex
from next_signal.integrations.coding_agents.discovery import resolve_executable
from next_signal.integrations.coding_agents.errors import CodingAgentProtocolError
from next_signal.integrations.coding_agents.types import (
    CodingAgentEvent,
    CodingAgentResult,
    CodingAgentRunRequest,
    ProviderName,
    ProviderParseState,
)

EventCallback = Callable[[CodingAgentEvent], None]

_SAFE_ENV = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
)


def validate_workspace(cwd: Path, config: CodingAgentsConfig) -> Path:
    requested = cwd.expanduser()
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    resolved = requested.resolve()
    if not resolved.is_dir():
        raise RuntimeError(f"coding-agent cwd is not a directory: {resolved}")
    roots = config.resolved_allowed_roots()
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        allowed = ", ".join(str(root) for root in roots)
        raise RuntimeError(
            f"coding-agent cwd {resolved} is outside configured allowed_roots: {allowed}"
        )
    return resolved


def build_child_env(settings: CodingAgentProviderConfig) -> dict[str, str]:
    names = {*_SAFE_ENV, *settings.inherit_env}
    if os.name == "nt":
        names.add("SystemRoot")
    return {name: os.environ[name] for name in names if name in os.environ}


def check_provider_version(
    provider: ProviderName,
    config: CodingAgentsConfig | None = None,
) -> tuple[bool, str]:
    cfg = config or load_coding_agents()
    settings = _settings(cfg, provider)
    if not settings.enabled:
        return True, "disabled"
    try:
        executable = resolve_executable(provider)
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            cwd=PROJECT_ROOT,
            env=build_child_env(settings),
            text=True,
            timeout=10,
        )
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    detail = (result.stdout or result.stderr).strip() or f"exit {result.returncode}"
    return result.returncode == 0, detail


async def run_coding_agent(
    request: CodingAgentRunRequest,
    *,
    config: CodingAgentsConfig | None = None,
    preferences: CodingAgentPreferences | None = None,
    on_event: EventCallback | None = None,
) -> CodingAgentResult:
    started = time.monotonic()
    cfg = config or load_coding_agents()
    provider = request.provider
    state = ProviderParseState()
    process: asyncio.subprocess.Process | None = None
    stderr_tail = ""
    runner_error: str | None = None
    timed_out = False

    try:
        cwd = validate_workspace(request.cwd, cfg)
        profile = cfg.profile(request.profile)
        settings = _settings(cfg, provider)
        if not settings.enabled:
            raise RuntimeError(f"coding-agent provider {provider!r} is disabled")
        runtime_preferences = preferences
        if runtime_preferences is None:
            runtime_preferences = load_coding_agent_preferences()
        executable = resolve_executable(provider)
        argv = _build_argv(
            provider,
            executable,
            profile,
            settings,
            runtime_preferences,
            request.json_schema,
        )
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=build_child_env(settings),
            start_new_session=os.name == "posix",
            limit=settings.max_event_bytes + 1,
        )
    except (OSError, RuntimeError, ValueError) as e:
        return _result(
            provider,
            state,
            started,
            process,
            error=str(e),
        )

    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    tasks = [
        asyncio.create_task(_write_prompt(process.stdin, request.prompt)),
        asyncio.create_task(
            _read_stdout(
                process.stdout,
                provider=provider,
                state=state,
                max_event_bytes=settings.max_event_bytes,
                on_event=on_event,
            )
        ),
    ]
    stderr_task = asyncio.create_task(_read_stderr(process.stderr, settings.max_stderr_chars))
    tasks.append(stderr_task)
    tasks.append(asyncio.create_task(process.wait()))

    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks),
            timeout=settings.timeout_seconds,
        )
        stderr_tail = stderr_task.result()
    except TimeoutError:
        timed_out = True
        runner_error = f"{provider} timed out after {settings.timeout_seconds:g}s"
        await _cancel_and_terminate(tasks, process, settings.terminate_grace_seconds)
        stderr_tail = _completed_stderr(stderr_task)
    except asyncio.CancelledError:
        await asyncio.shield(
            _cancel_and_terminate(tasks, process, settings.terminate_grace_seconds)
        )
        raise
    except Exception as e:  # protocol, callback, or pipe failure
        runner_error = f"{provider} protocol failure: {e}"
        await _cancel_and_terminate(tasks, process, settings.terminate_grace_seconds)
        stderr_tail = _completed_stderr(stderr_task)

    if runner_error is None:
        if process.returncode != 0:
            runner_error = state.error or f"{provider} exited with code {process.returncode}"
        elif not state.terminal_seen:
            runner_error = f"{provider} protocol failure: terminal event missing"
        elif not state.terminal_ok:
            runner_error = state.error or f"{provider} run failed"

    return _result(
        provider,
        state,
        started,
        process,
        error=runner_error,
        timed_out=timed_out,
        stderr=stderr_tail,
    )


async def _write_prompt(stream: asyncio.StreamWriter, prompt: str) -> None:
    stream.write(prompt.encode("utf-8"))
    await stream.drain()
    stream.close()
    await stream.wait_closed()


async def _read_stdout(
    stream: asyncio.StreamReader,
    *,
    provider: ProviderName,
    state: ProviderParseState,
    max_event_bytes: int,
    on_event: EventCallback | None,
) -> None:
    while True:
        try:
            line = await stream.readline()
        except (ValueError, asyncio.LimitOverrunError) as e:
            raise CodingAgentProtocolError(
                f"{provider} event exceeds {max_event_bytes} bytes"
            ) from e
        if not line:
            return
        if len(line) > max_event_bytes:
            raise CodingAgentProtocolError(f"{provider} event exceeds {max_event_bytes} bytes")
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise CodingAgentProtocolError(f"{provider} emitted malformed JSONL") from e
        if not isinstance(event, dict):
            raise CodingAgentProtocolError(f"{provider} event must be a JSON object")
        _consume(provider, event, state)
        if on_event is not None:
            on_event(
                CodingAgentEvent(
                    provider=provider,
                    session_id=state.session_id,
                    event=event,
                )
            )


async def _read_stderr(stream: asyncio.StreamReader, max_chars: int) -> str:
    tail = ""
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return tail
        if max_chars:
            tail = (tail + chunk.decode("utf-8", errors="replace"))[-max_chars:]


async def _cancel_and_terminate(
    tasks: list[asyncio.Task],
    process: asyncio.subprocess.Process,
    grace_seconds: float,
) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    await _terminate_process(process, grace_seconds)
    await asyncio.gather(*tasks, return_exceptions=True)


async def _terminate_process(
    process: asyncio.subprocess.Process,
    grace_seconds: float,
) -> None:
    if process.returncode is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    except PermissionError:
        # Some constrained launchers allow signalling the direct child but not
        # its newly created process group. Keep cleanup bounded in that case.
        try:
            process.terminate()
        except ProcessLookupError:
            return
    try:
        await asyncio.wait_for(process.wait(), timeout=grace_seconds)
        return
    except TimeoutError:
        pass
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        return
    except PermissionError:
        try:
            process.kill()
        except ProcessLookupError:
            return
    await process.wait()


def _completed_stderr(task: asyncio.Task[str]) -> str:
    if task.done() and not task.cancelled():
        try:
            return task.result()
        except Exception:  # noqa: BLE001
            return ""
    return ""


def _settings(
    config: CodingAgentsConfig,
    provider: ProviderName,
) -> CodingAgentProviderConfig:
    return config.providers.codex if provider == "codex" else config.providers.claude


def _build_argv(
    provider,
    executable,
    profile,
    settings,
    preferences: CodingAgentPreferences,
    json_schema: dict | None,
) -> list[str]:
    if provider == "codex":
        return codex.build_argv(
            executable,
            profile,
            settings,
            preferences.codex,
            json_schema=json_schema,
        )
    return claude.build_argv(
        executable,
        profile,
        settings,
        preferences.claude,
        json_schema=json_schema,
    )


def _consume(
    provider: ProviderName,
    event: dict,
    state: ProviderParseState,
) -> None:
    if provider == "codex":
        codex.consume_event(event, state)
    else:
        claude.consume_event(event, state)


def _result(
    provider: ProviderName,
    state: ProviderParseState,
    started: float,
    process: asyncio.subprocess.Process | None,
    *,
    error: str | None,
    timed_out: bool = False,
    stderr: str = "",
) -> CodingAgentResult:
    return CodingAgentResult(
        ok=error is None,
        provider=provider,
        session_id=state.session_id,
        text=state.text,
        usage=state.usage,
        returncode=process.returncode if process is not None else None,
        duration_ms=max(0, round((time.monotonic() - started) * 1000)),
        timed_out=timed_out,
        stderr=stderr,
        error=error,
    )
