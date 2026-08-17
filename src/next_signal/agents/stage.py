"""Provider-neutral execution for production LLM workflow stages."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from collections.abc import Iterator
from typing import TypeVar

from pydantic import BaseModel

from next_signal.agents.loader import _compose_instructions, build_from_config
from next_signal.agents.structured import parse_structured, repair_prompt
from next_signal.core.coding_agent_preferences import (
    CodingAgentPreferences,
    load_coding_agent_preferences,
)
from next_signal.core.concurrency import ProviderConcurrency
from next_signal.core.config import AgentConfig, CodingAgentsConfig, load_agent, load_coding_agents
from next_signal.core.engine_preferences import (
    Engine,
    EngineNotSelected,
    EnginePreferences,
    load_engine_preferences,
)
from next_signal.core.logging import get_logger
from next_signal.core.models import ensure_concurrency_configured, get_stage_model
from next_signal.core.paths import AGENT_TMP_DIR
from next_signal.integrations.coding_agents.runner import run_coding_agent
from next_signal.integrations.coding_agents.types import (
    CodingAgentResult,
    CodingAgentRunRequest,
)

T = TypeVar("T", bound=BaseModel)
log = get_logger(__name__)


class StageInvocationError(RuntimeError):
    """The selected provider failed before returning a usable response."""


@dataclass
class StageJobState:
    preferences: EnginePreferences
    selected: Engine
    # Read once, with `preferences`, and reused by every stage in the job. A job
    # can run for an hour, and the settings page can be edited inside it; a CLI
    # model re-read per stage would score the first half of a batch with one
    # model and the second half with another, silently, while the scores are
    # compared against each other.
    coding_agents: CodingAgentPreferences
    locked: bool = False
    initial_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


def stage_job_provenance(state: StageJobState) -> dict[str, object]:
    """Serializable engine/model settings actually used by an evaluation job."""
    result: dict[str, object] = {
        "selected": state.selected,
        "locked": state.locked,
        "selection": {
            "primary": state.preferences.primary,
            "fallback": state.preferences.fallback,
        },
    }
    if state.selected == "omlx":
        result["engine"] = state.preferences.omlx.model_dump(mode="json")
    elif state.selected == "deepseek":
        result["engine"] = state.preferences.deepseek.model_dump(mode="json")
    else:
        cli = state.coding_agents
        selected = cli.codex if state.selected == "codex_cli" else cli.claude
        result["coding_agent"] = (
            selected.model_dump(mode="json") if selected is not None else None
        )
    return result


_STAGE_JOB: ContextVar[StageJobState | None] = ContextVar("stage_job", default=None)


@contextmanager
def stage_job(
    preferences: EnginePreferences | None = None,
    *,
    state: StageJobState | None = None,
) -> Iterator[StageJobState]:
    """Pin or re-bind one engine selection for a complete production job."""
    current = _STAGE_JOB.get()
    if current is not None:
        if state is not None and current is not state:
            raise RuntimeError("cannot bind a different stage job inside an active job")
        yield current
        return

    if preferences is not None and state is not None:
        raise ValueError("stage_job accepts preferences or state, not both")
    if state is None:
        selected = preferences or load_engine_preferences()
        if selected.primary is None:
            raise EngineNotSelected(
                "No engine has been selected, so this job cannot run. "
                "Choose one on the dashboard settings page (Settings -> Engine)."
            )
        ensure_concurrency_configured()
        ProviderConcurrency.set_limit("omlx", selected.omlx.parallel)
        state = StageJobState(
            preferences=selected,
            selected=selected.primary,
            coding_agents=load_coding_agent_preferences(),
        )
    token = _STAGE_JOB.set(state)
    try:
        yield state
    finally:
        _STAGE_JOB.reset(token)


def run_stage(
    agent_name: str,
    agent_input: str,
    output_schema: type[T] | None = None,
    *,
    language: str | None = None,
) -> T | str:
    """Run one configured production stage on the job-selected engine."""
    state = _STAGE_JOB.get()
    if state is None:
        with stage_job():
            return run_stage(
                agent_name,
                agent_input,
                output_schema,
                language=language,
            )

    cfg = load_agent(agent_name)
    if cfg.tools:
        raise RuntimeError(
            f"{agent_name}: production stage adapter does not expose agent tools"
        )

    content = _invoke_with_affinity(
        state,
        cfg,
        agent_input,
        output_schema,
        language,
    )
    if output_schema is None:
        text = "" if content is None else str(content)
        if not text.strip():
            raise RuntimeError(f"{agent_name} returned empty text")
        return text

    last_error = ""
    raw = str(content)
    try:
        return parse_structured(content, output_schema)
    except ValueError as exc:
        last_error = str(exc)

    repaired = repair_prompt(agent_input, raw, last_error)
    content = _invoke_pinned(
        state,
        cfg,
        repaired,
        output_schema,
        language,
    )
    try:
        return parse_structured(content, output_schema)
    except ValueError as exc:
        raise RuntimeError(
            f"{agent_name} could not produce a valid {output_schema.__name__}: {exc}"
        ) from exc


def _invoke_with_affinity(
    state: StageJobState,
    cfg: AgentConfig,
    agent_input: str,
    output_schema: type[BaseModel] | None,
    language: str | None,
) -> object:
    if state.locked:
        return _invoke_engine(
            state.selected, state, cfg, agent_input, output_schema, language
        )

    # Only the first successful provider response decides affinity. Other
    # threads wait for that one decision, then regain normal parallelism.
    with state.initial_lock:
        if state.locked:
            return _invoke_engine(
                state.selected,
                state,
                cfg,
                agent_input,
                output_schema,
                language,
            )
        engine = state.selected
        used_fallback = False
        try:
            content = _invoke_engine(
                engine, state, cfg, agent_input, output_schema, language
            )
        except StageInvocationError:
            fallback = state.preferences.fallback
            if fallback == "none":
                raise
            engine = fallback
            used_fallback = True
            content = _invoke_engine(
                engine, state, cfg, agent_input, output_schema, language
            )
        state.selected = engine
        state.locked = True
        log.info("stage_engine_selected", engine=engine, fallback=used_fallback)
        return content


def _invoke_pinned(
    state: StageJobState,
    cfg: AgentConfig,
    agent_input: str,
    output_schema: type[BaseModel] | None,
    language: str | None,
) -> object:
    if not state.locked:
        raise RuntimeError("stage provider must be pinned before schema repair")
    return _invoke_engine(
        state.selected, state, cfg, agent_input, output_schema, language
    )


def _invoke_engine(
    engine: Engine,
    state: StageJobState,
    cfg: AgentConfig,
    agent_input: str,
    output_schema: type[BaseModel] | None,
    language: str | None,
) -> object:
    # `engine` is passed separately from `state`: during the affinity decision it
    # is the candidate being tried, which is not yet `state.selected`.
    if engine in {"omlx", "deepseek"}:
        return _invoke_api(
            engine, state.preferences, cfg, agent_input, output_schema, language
        )
    return _invoke_cli(
        engine, state.coding_agents, cfg, agent_input, output_schema, language
    )


def _invoke_api(
    engine: Engine,
    preferences: EnginePreferences,
    cfg: AgentConfig,
    agent_input: str,
    output_schema: type[BaseModel] | None,
    language: str | None,
) -> object:
    try:
        model = get_stage_model(
            engine,
            preferences,
            structured=output_schema is not None,
        )
        agent = build_from_config(cfg, language=language, model=model)
        response = agent.run(agent_input, output_schema=output_schema)
    except Exception as exc:
        raise StageInvocationError(f"{engine} stage invocation failed: {exc}") from exc
    return getattr(response, "content", response)


def _invoke_cli(
    engine: Engine,
    preferences: CodingAgentPreferences,
    cfg: AgentConfig,
    agent_input: str,
    output_schema: type[BaseModel] | None,
    language: str | None,
) -> object:
    provider = "codex" if engine == "codex_cli" else "claude"
    schema = output_schema.model_json_schema() if output_schema is not None else None
    prompt = _cli_prompt(cfg, agent_input, language=language, json_schema=schema)
    try:
        workspace_root = _stage_workspace_root()
        workspace_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with TemporaryDirectory(prefix="run-", dir=workspace_root) as workspace:
            cwd = Path(workspace)
            request = CodingAgentRunRequest(
                provider=provider,
                prompt=prompt,
                cwd=cwd,
                profile="stage",
                json_schema=schema,
            )
            runtime_config = _isolated_stage_config(cwd)
            with ProviderConcurrency.acquire_sync(engine):
                result = _run_cli(request, runtime_config, preferences)
    except Exception as exc:
        raise StageInvocationError(f"{engine} stage invocation failed: {exc}") from exc
    if not result.ok:
        raise StageInvocationError(
            f"{engine} stage invocation failed: {result.error or result.stderr}"
        )
    return result.text


def _run_cli(
    request: CodingAgentRunRequest,
    config: CodingAgentsConfig,
    preferences: CodingAgentPreferences,
) -> CodingAgentResult:
    """Drive the async runner from sync stage code, live event loop or not.

    AgentOS reaches a production stage through ``Workflow.arun``, and agno runs a
    sync step executor inline on the loop thread — so a bare ``asyncio.run`` here
    raises, and the affinity layer above reads that as "this engine is
    unavailable" and quietly falls back. A one-shot thread gets its own loop.
    Blocking on it costs no more than agno already spends running the step inline.
    """

    def call() -> CodingAgentResult:
        return asyncio.run(
            run_coding_agent(request, config=config, preferences=preferences)
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return call()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(call).result()


def _stage_workspace_root() -> Path:
    return AGENT_TMP_DIR / "coding-agent-stage"


def _isolated_stage_config(cwd: Path) -> CodingAgentsConfig:
    """Restrict runner validation to this one ephemeral stage directory."""
    configured = load_coding_agents()
    return configured.model_copy(update={"allowed_roots": [str(cwd)]})


def _cli_prompt(
    cfg: AgentConfig,
    agent_input: str,
    *,
    language: str | None,
    json_schema: dict | None,
) -> str:
    sections = [
        "# Stage instructions\n\n" + _compose_instructions(cfg, override=language),
        (
            "# Runtime constraints\n\n"
            "Complete this stage only from the input below. Do not inspect repository "
            "files, invoke tools, run commands, or modify anything."
        ),
        "# Stage input\n\n" + agent_input,
    ]
    if json_schema is not None:
        sections.append(
            "# Output contract\n\nReturn only JSON matching this schema:\n"
            + json.dumps(json_schema, ensure_ascii=False, separators=(",", ":"))
        )
    return "\n\n---\n\n".join(sections)
