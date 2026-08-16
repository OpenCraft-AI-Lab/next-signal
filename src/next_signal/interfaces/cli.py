"""``next-signal`` CLI — entrypoint for local debugging, manual workflow runs, and
quick agent invocation. Subcommands are added incrementally as features land.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import typer
from dotenv import load_dotenv

from next_signal.core.config import list_agents, list_teams, list_workflows
from next_signal.core.logging import configure as configure_logging
from next_signal.core.paths import PROJECT_ROOT
from next_signal.core.secrets import get_secret

app = typer.Typer(no_args_is_help=True, add_completion=False)
knowledge_app = typer.Typer(help="Manage knowledge adapters and GBrain.")
info_radar_app = typer.Typer(help="Pull and sweep the info-radar collector.")
coding_agent_app = typer.Typer(help="Run optional Codex or Claude Code CLI workers.")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(info_radar_app, name="info-radar")
app.add_typer(coding_agent_app, name="coding-agent")


def _check_folocli() -> tuple[str, bool, str]:
    """Verify folocli auth for `next-signal doctor`.

    ``FOLO_TOKEN`` from the credential store is the only accepted source; a
    cached folocli session no longer counts as authenticated.
    """
    from next_signal.integrations.info_radar.folo import whoami

    ok, msg = whoami()
    return ("folocli", ok, msg)


def _check_goals_yaml() -> tuple[str, bool, str]:
    """Verify the runtime goals file loads. No LLM call.

    Three failures, three messages: "not set up yet", "you cleared them", and "the
    file is broken" call for different reactions, and the middle one is a state the
    operator can deliberately save — so it must not read as corruption.
    """
    import yaml

    from next_signal.workflows.info_radar_analysis.goals import goals_path, load_goals

    label = "info-radar goals"
    path = goals_path()
    if not path.exists():
        return (label, False, f"no goals file at {path}")
    try:
        goals = load_goals(path)
    except Exception as e:  # noqa: BLE001
        # Distinguish a deliberately emptied list from a parse/validation error
        # without duplicating the loader's schema rules here. A hand-edited file
        # left as a bare `goals:` is null, not `[]`, and means the same thing.
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            emptied = isinstance(raw, dict) and "goals" in raw and raw["goals"] in (None, [])
        except Exception:  # noqa: BLE001
            emptied = False
        if emptied:
            return (label, False, f"no goals configured at {path}; add one on /goals")
        return (label, False, str(e))
    return (label, True, f"{len(goals)} goal(s) at {path}")


def _check_embedder() -> tuple[str, bool, str]:
    """Report the active vector-space identity and whether its key is present.

    Configuration only — no embedding request is made, so this check never
    spends money or GPU. It answers "will the 08:00 scheduler be able to embed",
    not "is the endpoint up".
    """
    from next_signal.core.embedding_preferences import (
        embedder_identity,
        load_embedding_preferences,
    )

    try:
        prefs = load_embedding_preferences()
    except RuntimeError as e:
        return ("embedder", False, str(e))
    identity = embedder_identity(prefs)

    if prefs.provider == "omlx":
        from next_signal.core.models import omlx_endpoint

        # OMLX_API_KEY stays optional — the local server usually has none —
        # so only the base URL can fail this check.
        try:
            return ("embedder", True, f"{identity} at {omlx_endpoint()['base_url']}")
        except RuntimeError as e:
            return ("embedder", False, f"{identity} — {e}")

    if prefs.provider == "openai":
        variable, where = "OPENAI_API_KEY", "https://api.openai.com/v1"
    else:
        variable = prefs.openai_compatible.api_key_env
        where = prefs.openai_compatible.base_url
    if not get_secret(variable):
        return (
            "embedder",
            False,
            f"{identity} — {variable} is not configured; set it on the dashboard "
            "settings page (Settings → Credentials)",
        )
    return ("embedder", True, f"{identity} at {where} ({variable} set)")


def _check_gbrain() -> tuple[str, bool, str]:
    from next_signal.integrations.gbrain import gbrain_env

    gbrain_bin = os.environ.get("GBRAIN_BIN", "").strip() or shutil.which("gbrain")
    if not gbrain_bin:
        return (
            "GBrain",
            False,
            "gbrain CLI not found; install/link gbrain or set GBRAIN_BIN",
        )
    try:
        result = subprocess.run(
            [gbrain_bin, "doctor", "--fast"],
            check=False,
            capture_output=True,
            env=gbrain_env(),
            text=True,
            timeout=10,
        )
        ok = result.returncode == 0
        msg = (result.stdout or result.stderr).strip() or f"exit {result.returncode}"
        return ("GBrain", ok, msg)
    except Exception as e:  # noqa: BLE001
        return ("GBrain", False, f"unhealthy: {e}")


@app.callback()
def _root() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    configure_logging()


@app.command("list")
def list_cmd() -> None:
    """List all configured agents and workflows."""
    typer.echo("Agents:")
    for name in list_agents():
        typer.echo(f"  - {name}")
    typer.echo("Workflows:")
    for name in list_workflows():
        typer.echo(f"  - {name}")
    typer.echo("Teams:")
    for name in list_teams():
        typer.echo(f"  - {name}")


@app.command("serve")
def serve(port: int = 7777, reload: bool = True) -> None:
    """Run AgentOS locally."""
    import uvicorn

    uvicorn.run("next_signal.os_app:app", host="127.0.0.1", port=port, reload=reload)


@app.command("schedule")
def schedule() -> None:
    """Run the wall-clock scheduler in the foreground until interrupted.

    The command for the `scheduler` container service. No flags: the schedule
    lives in `~/.next-signal/schedule.json` so the dashboard and the operator
    edit one source of truth, and it is re-read on every poll.
    """
    from next_signal.orchestrator.schedule import run

    run()


@app.command("dashboard")
def dashboard(
    build: bool = typer.Option(False, "--build", help="Run `pnpm build` instead of dev"),
    start: bool = typer.Option(
        False, "--start", help="Run `pnpm start` (production server, requires prior --build)"
    ),
    port: int = typer.Option(3000, help="Port for the Next.js server"),
) -> None:
    """Run the Next.js dashboard from ``dashboard/``.

    The dashboard is fully decoupled from ``next-signal serve`` — its server actions
    spawn ``next-signal`` CLI children directly, and its data layer reads Postgres
    via ``pg``. You only need ``next-signal serve`` running when something on the
    page actually talks to AgentOS HTTP endpoints (none today).

    This subcommand is a thin wrapper over ``pnpm`` so the operator has a
    single ``next-signal`` entrypoint.
    """
    pnpm = shutil.which("pnpm")
    if not pnpm:
        typer.secho(
            "`pnpm` not found on PATH. Install Node 20+ and `npm install -g pnpm`.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    cwd = PROJECT_ROOT / "dashboard"
    if not (cwd / "package.json").is_file():
        typer.secho(f"dashboard/package.json missing under {cwd}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    if build and start:
        typer.secho("--build and --start are mutually exclusive", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    if build:
        argv = [pnpm, "build"]
    elif start:
        argv = [pnpm, "start", "-p", str(port)]
    else:
        argv = [pnpm, "dev", "-p", str(port)]
    # exec-style replacement so signals (Ctrl-C, SIGTERM) reach pnpm
    # directly and we don't leak a python middleman on the process tree.
    # `execvp` inherits cwd, so chdir first — pnpm scans cwd for package.json.
    os.chdir(cwd)
    os.execvp(argv[0], argv)


@app.command("run-agent")
def run_agent(
    name: str = typer.Argument(..., help="Agent name (see `next-signal list`)"),
    prompt: str = typer.Argument(..., help="Prompt to send to the agent"),
    stream: bool = typer.Option(True, help="Stream response tokens to stdout"),
) -> None:
    """One-shot agent invocation without starting AgentOS."""
    from next_signal.agents.loader import build_from_name

    agent = build_from_name(name)
    if stream:
        agent.print_response(prompt, stream=True)
    else:
        result = agent.run(prompt)
        typer.echo(result.content if hasattr(result, "content") else str(result))


@coding_agent_app.command("doctor")
def coding_agent_doctor() -> None:
    """Check configured coding-agent binaries without making a model request."""
    from next_signal.core.config import load_coding_agents
    from next_signal.integrations.coding_agents.runner import check_provider_version

    try:
        cfg = load_coding_agents()
    except Exception as e:  # noqa: BLE001 — config errors are operator output
        typer.echo(f"✗ coding-agent config: {e}", err=True)
        raise typer.Exit(code=1) from e

    failed = False
    for provider in ("codex", "claude"):
        ok, detail = check_provider_version(provider, cfg)
        typer.echo(f"{'✓' if ok else '✗'} {provider}: {detail}")
        failed = failed or not ok
    if failed:
        raise typer.Exit(code=1)


def _validated_coding_agent_provider(provider: str) -> str:
    if provider not in {"codex", "claude"}:
        typer.echo(
            f"unknown coding-agent provider {provider!r}; valid providers: claude, codex",
            err=True,
        )
        raise typer.Exit(code=2)
    return provider


@coding_agent_app.command("auth-status", hidden=True)
def coding_agent_auth_status(provider: str = typer.Argument(...)) -> None:
    """Emit sanitized provider login status for the local Dashboard."""
    import json

    from next_signal.integrations.coding_agents.auth import check_auth_status

    selected = _validated_coding_agent_provider(provider)
    status = check_auth_status(selected)
    typer.echo(json.dumps(status, ensure_ascii=False, separators=(",", ":")))
    if not status["available"]:
        raise typer.Exit(code=1)


@coding_agent_app.command("auth-login", hidden=True)
def coding_agent_auth_login(provider: str = typer.Argument(...)) -> None:
    """Run one bounded PTY login session using a fixed provider command."""
    import json
    import sys

    from next_signal.integrations.coding_agents.auth import run_login_session

    selected = _validated_coding_agent_provider(provider)

    def emit(event: dict[str, object]) -> None:
        typer.echo(json.dumps(event, ensure_ascii=False, separators=(",", ":")))

    result = run_login_session(selected, emit=emit, input_stream=sys.stdin)
    if not result["ok"]:
        raise typer.Exit(code=1)


@coding_agent_app.command("auth-logout", hidden=True)
def coding_agent_auth_logout(provider: str = typer.Argument(...)) -> None:
    """Remove one provider's saved login through its fixed logout command."""
    import json

    from next_signal.integrations.coding_agents.auth import logout

    selected = _validated_coding_agent_provider(provider)
    result = logout(selected)
    typer.echo(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    if not result["ok"]:
        raise typer.Exit(code=1)


@coding_agent_app.command("run")
def coding_agent_run(
    provider: str = typer.Argument(..., help="Provider: codex or claude"),
    prompt: str = typer.Argument(..., help="Repository task prompt"),
    cwd: Path = typer.Option(..., "--cwd", help="Repository working directory"),
    profile: str | None = typer.Option(
        None, "--profile", help="Execution profile (default: configured review profile)"
    ),
    progress: bool = typer.Option(
        False, "--progress", help="Emit provider events and final result as JSONL"
    ),
) -> None:
    """Run one bounded, non-persistent coding-agent task."""
    import asyncio

    from next_signal.core.config import load_coding_agents
    from next_signal.integrations.coding_agents.runner import run_coding_agent
    from next_signal.integrations.coding_agents.types import (
        CodingAgentEvent,
        CodingAgentRunRequest,
    )

    _validated_coding_agent_provider(provider)

    try:
        cfg = load_coding_agents()
        cfg.profile(profile)
        request = CodingAgentRunRequest(
            provider=provider,
            prompt=prompt,
            cwd=cwd,
            profile=profile,
        )
    except Exception as e:  # noqa: BLE001 — validation errors are operator output
        typer.echo(f"coding-agent: {e}", err=True)
        raise typer.Exit(code=2) from e

    def emit(event: CodingAgentEvent) -> None:
        typer.echo(event.model_dump_json())

    result = asyncio.run(
        run_coding_agent(
            request,
            config=cfg,
            on_event=emit if progress else None,
        )
    )
    if progress:
        typer.echo(result.model_dump_json())
    else:
        import json

        typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    if not result.ok:
        raise typer.Exit(code=1)


@app.command("doctor")
def doctor() -> None:
    """Check that the environment is set up enough to run the system."""
    checks: list[tuple[str, bool, str]] = []

    # 1. .env essentials (system connection config only — credentials are below)
    db = os.environ.get("DATABASE_URL")
    checks.append(("DATABASE_URL", bool(db), db or "not set"))

    # 1b. Credentials, from the store. Presence only — a value is never printed.
    # Only the two the default configuration depends on are hard checks; the
    # rest are covered by the feature checks that actually need them (embedder,
    # folocli) or are optional by contract (GITHUB_TOKEN, OMLX_API_KEY).
    for name, consequence in (
        ("ANTHROPIC_API_KEY", "claude_* profiles will fail"),
        ("DEEPSEEK_API_KEY", "local* fallback to deepseek will fail"),
    ):
        present = bool(get_secret(name))
        checks.append((name, present, "set" if present else f"not configured ({consequence})"))

    # 2. OMLX endpoint (centralized in next_signal.core.models.omlx_endpoint)
    from next_signal.core.models import omlx_endpoint

    try:
        omlx_url = omlx_endpoint()["base_url"]
    except RuntimeError:
        omlx_url = ""
    checks.append(
        (
            "OMLX_BASE_URL",
            bool(omlx_url),
            omlx_url or "not set (omlx profiles will fail to fallback_profile)",
        )
    )

    # 2b. Output language (global policy). A missing preference file is a
    # valid, unchanged-behavior state, so this reports rather than fails; a
    # corrupt or unrecognized preference-file value raises and is surfaced.
    from next_signal.core.language import LANGUAGE_STATE_FILE, global_language

    try:
        lang = global_language()
        checks.append(
            (
                "content language",
                True,
                f"{lang} ({'from ' + str(LANGUAGE_STATE_FILE) if LANGUAGE_STATE_FILE.exists() else 'hardcoded default'})",
            )
        )
    except RuntimeError as e:
        checks.append(("content language", False, str(e)))

    # 2c. Which embedder the dedup gate will resolve, and whether its
    # credential is in *this* process. The scheduler embeds unattended, and a
    # hosted provider with no key turns every item into `novel` with nobody
    # reading the logs live.
    checks.append(_check_embedder())

    # 3. Postgres reachable, and is its schema current?
    # Reachability alone is not health: a stack running a pre-migration image
    # answers SELECT 1 happily while the dashboard 500s on a missing column.
    from next_signal.core.db import missing_business_columns

    db_ok = False
    db_msg = "skipped (no DATABASE_URL)"
    schema_check: tuple[str, bool, str] | None = None
    if db:
        try:
            import psycopg

            with psycopg.connect(db, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                db_ok = True
                db_msg = "reachable"
                gaps = missing_business_columns(conn)
            schema_check = (
                ("business schema", True, "all expected columns present")
                if not gaps
                else (
                    "business schema",
                    False,
                    "; ".join(f"{t} missing {', '.join(c)}" for t, c in gaps.items())
                    + " — re-run scripts/bootstrap_db.py (rebuild the image first)",
                )
            )
        except Exception as e:  # noqa: BLE001
            db_msg = f"unreachable: {e}"
    checks.append(("Postgres", db_ok, db_msg))
    if schema_check:
        checks.append(schema_check)

    # 4. configs / agents present?
    agents = list_agents()
    checks.append(("configured agents", bool(agents), ", ".join(agents) or "none"))

    # 5. tool registry imports
    from next_signal import registry

    available = registry.available()
    checks.append(("registered tools", bool(available), f"{len(available)} tools"))

    # 6. GBrain CLI / service health
    checks.append(_check_gbrain())

    # 6b. folocli auth (info-radar collector)
    checks.append(_check_folocli())

    # 6c. info-radar analysis goals present and non-empty?
    checks.append(_check_goals_yaml())

    # Print results.
    width = max(len(n) for n, _, _ in checks)
    for name_, ok, msg in checks:
        marker = "✔" if ok else "✗"
        typer.echo(f"  {marker}  {name_:<{width}}  {msg}")

    bad = [n for n, ok, _ in checks if not ok]
    raise typer.Exit(code=0 if not bad else 1)


@knowledge_app.command("gbrain-search")
def knowledge_gbrain_search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(5, min=1, max=20, help="Maximum results."),
) -> None:
    """Search GBrain through the local CLI bridge."""
    import json

    from next_signal.tools.gbrain import gbrain_search

    typer.echo(json.dumps(gbrain_search.entrypoint(query, limit), ensure_ascii=False, indent=2))


@knowledge_app.command("gbrain-ingest")
def knowledge_gbrain_ingest(
    path: str = typer.Argument(..., help="Markdown file or directory to import."),
) -> None:
    """Import markdown into GBrain through the local CLI bridge."""
    import json

    from next_signal.tools.gbrain import gbrain_ingest

    typer.echo(json.dumps(gbrain_ingest.entrypoint(path), ensure_ascii=False, indent=2))


@knowledge_app.command("init-test-gbrain")
def knowledge_init_test_gbrain(
    home: Path = typer.Option(
        PROJECT_ROOT / "state" / "test-gbrain",
        "--home",
        help="Parent directory for the isolated test GBrain home.",
    ),
) -> None:
    """Initialize an isolated local GBrain PGLite database for integration tests."""
    from next_signal.integrations.gbrain import _gbrain_bin, gbrain_env, resolve_gbrain_home

    resolved_home = resolve_gbrain_home(str(home))
    db_path = Path(resolved_home) / ".gbrain" / "brain.pglite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [_gbrain_bin(), "init", "--pglite", "--path", str(db_path)],
        check=False,
        capture_output=True,
        env=gbrain_env(gbrain_home=resolved_home),
        text=True,
        timeout=120,
    )
    if result.stdout.strip():
        typer.echo(result.stdout.strip())
    if result.stderr.strip():
        typer.echo(result.stderr.strip(), err=True)
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)

    typer.echo(f"GBRAIN_HOME={resolved_home}")
    typer.echo(f"GBRAIN database: {db_path}")


@knowledge_app.command("ingest")
def knowledge_ingest_cmd(
    value: str = typer.Argument(..., help="URL or staged local file to ingest."),
    ingest: bool = typer.Option(True, help="Import the clean markdown into GBrain."),
    category: str | None = typer.Option(
        None, help="Pin the destination wiki folder (taxonomy path); skips auto-classify."
    ),
    progress: bool = typer.Option(
        False, help="Emit one JSON event per pipeline step to stdout (JSONL)."
    ),
) -> None:
    """Ingest one URL or file as a durable markdown artifact."""
    import json
    import sys

    from next_signal.workflows.knowledge_ingest import ingest_one

    on_progress = None
    if progress:
        # Each event is one JSON line on stdout. structlog logs render as their
        # own JSON objects (a different shape); the dashboard runner consumes
        # this stream and skips any line that isn't a step-event / result.
        def on_progress(event: dict) -> None:
            sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    result = ingest_one(value, ingest=ingest, category=category, on_progress=on_progress)

    if progress:
        # Final line is the result object — N event lines + 1 result line = valid JSONL.
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    else:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@knowledge_app.command("review")
def knowledge_review_cmd() -> None:
    """Reconcile the wiki against knowledge_reviews (enroll new docs, unenroll gone ones)."""
    from next_signal.workflows.knowledge_review import run as run_review

    try:
        result = run_review()
    except RuntimeError as e:
        typer.echo(f"knowledge review: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(
        f"knowledge review: enrolled={result['enrolled']} "
        f"unenrolled={result['unenrolled']} due={result['due']}"
    )


@app.command("run-workflow")
def run_workflow(name: str = typer.Argument(..., help="Workflow config name.")) -> None:
    """Run one workflow immediately via its ``extra.run_now`` entry point.

    The dashboard uses this to trigger jobs (e.g. the knowledge re-index) from
    the UI. `next-signal schedule` drives the radar chain on a wall clock; the
    re-index is deliberately not on it.
    """
    import json

    from next_signal.orchestrator.run_now import run_workflow_now

    result = run_workflow_now(name)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@info_radar_app.command("pull")
def info_radar_pull(
    source: str | None = typer.Option(
        None, "--source", help="Pull only this source (default: every enabled source)."
    ),
) -> None:
    """Invoke each enabled source's CLI, parse stdout, and upsert to radar_items."""
    from next_signal.collectors.info_radar.runner import all_failed, run_all

    results = run_all(only=source)
    if not results:
        typer.echo("(no sources to run)")
        raise typer.Exit(code=0)
    for r in results:
        if r.error:
            typer.echo(f"{r.name}: ERROR — {r.error}", err=True)
        else:
            typer.echo(f"{r.name}: written={r.written} skipped={r.skipped}")
    raise typer.Exit(code=1 if all_failed(results) else 0)


@info_radar_app.command("sweep")
def info_radar_sweep() -> None:
    """Delete radar_items rows older than 30 days. Reports the row count."""
    from next_signal.collectors.info_radar import store

    deleted = store.sweep_expired()
    typer.echo(f"deleted {deleted} expired row(s)")


@info_radar_app.command("analyze")
def info_radar_analyze(
    limit: int | None = typer.Option(
        None, "--limit", min=1, help="Maximum unseen items to process this run."
    ),
    source: str | None = typer.Option(
        None, "--source", help="Restrict to one collector source name."
    ),
) -> None:
    """Run the two-tier analysis pipeline over unseen radar_items."""
    from next_signal.workflows.info_radar_analysis import run as run_analysis

    counters = run_analysis(limit=limit, source=source)
    parts = [f"{k}={v}" for k, v in counters.items()]
    typer.echo("info-radar analyze: " + " ".join(parts))


@info_radar_app.command("recap")
def info_radar_recap(
    since: str = typer.Option(..., "--since", help="Range start, YYYY-MM-DD (inclusive)."),
    until: str = typer.Option(..., "--until", help="Range end, YYYY-MM-DD (inclusive)."),
    min_score: int = typer.Option(
        0, "--min-score", min=0, max=100, help="Quality gate: minimum analysis score."
    ),
    novel_only: bool = typer.Option(
        False, "--novel-only", help="Restrict to items the dedup gate marked novel."
    ),
    regenerate: bool = typer.Option(
        False, "--regenerate", help="Recompute even when a recap is already cached."
    ),
) -> None:
    """Synthesize a date range of kept signals into themed narratives."""
    from next_signal.workflows.info_radar_recap import run as run_recap

    try:
        result = run_recap(
            since=since,
            until=until,
            min_score=min_score,
            novel_only=novel_only,
            regenerate=regenerate,
        )
    except RuntimeError as e:
        typer.echo(f"info-radar recap: {e}", err=True)
        raise typer.Exit(code=1) from e

    status = result["status"]
    if status == "empty":
        typer.echo(
            f"info-radar recap: no items cleared the gate for {result['since']}..{result['until']}"
        )
        return
    if status == "running":
        typer.echo("info-radar recap: a generation is already running for this range")
        return
    if status == "error":
        typer.echo(f"info-radar recap: FAILED — {result['error']}", err=True)
        raise typer.Exit(code=1)

    origin = "cached" if status == "cached" else "generated"
    typer.echo(f"info-radar recap ({origin}): {result['headline']}")
    for theme in result["themes"]:
        typer.echo(f"  · {theme['title']} [{len(theme['item_ids'])} cited]")
    shown, considered = result.get("item_count"), result.get("considered_count")
    if shown and considered and considered > shown:
        typer.echo(f"  (synthesized from the top {shown} of {considered} signals)")


@info_radar_app.command("subscriptions")
def info_radar_subscriptions(
    json_output: bool = typer.Option(
        False, "--json", help="Print normalized subscription rows as JSON."
    ),
) -> None:
    """List Folo subscriptions through the pinned folocli bridge."""
    import json

    from next_signal.integrations.info_radar.folo import subscription_list

    rows = subscription_list()
    if json_output:
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        unread = row.get("unread")
        unread_text = "" if unread is None else f"\t unread={unread}"
        typer.echo(
            f"{row.get('title', '(untitled)')}\t{row.get('category', 'Uncategorized')}"
            f"\t{row.get('feedUrl', '')}{unread_text}"
        )


if __name__ == "__main__":
    app()
