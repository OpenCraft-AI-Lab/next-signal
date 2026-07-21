"""``paca`` CLI — entrypoint for local debugging, manual workflow runs, and
quick agent invocation. Subcommands are added incrementally as features land.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import typer
from dotenv import load_dotenv

from paca.core.config import list_agents, list_teams, list_workflows
from paca.core.logging import configure as configure_logging
from paca.core.paths import PROJECT_ROOT

app = typer.Typer(no_args_is_help=True, add_completion=False)
knowledge_app = typer.Typer(help="Manage knowledge adapters and GBrain.")
info_radar_app = typer.Typer(help="Pull and sweep the info-radar collector.")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(info_radar_app, name="info-radar")


def _check_folocli() -> tuple[str, bool, str]:
    """Verify folocli auth (FOLO_TOKEN env OR cached session) for `paca doctor`."""
    from paca.integrations.info_radar.folo import whoami

    ok, msg = whoami()
    return ("folocli", ok, msg)


def _check_goals_yaml() -> tuple[str, bool, str]:
    """Verify ``configs/info_radar/goals.yaml`` loads. No LLM call."""
    from paca.workflows.info_radar_analysis.goals import goals_path, load_goals

    path = goals_path()
    if not path.exists():
        return (
            "info-radar goals.yaml",
            False,
            f"missing at {path}; copy goals.example.yaml to goals.yaml",
        )
    try:
        goals = load_goals(path)
    except Exception as e:  # noqa: BLE001
        return ("info-radar goals.yaml", False, str(e))
    return ("info-radar goals.yaml", True, f"{len(goals)} goal(s)")


def _check_gbrain() -> tuple[str, bool, str]:
    from paca.integrations.gbrain import gbrain_env

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


def _run_workflow_now(workflow: str, inputs: dict | None = None) -> dict:
    from paca.core.config import load_workflow
    from paca.orchestrator.runnable_loader import load_factory

    try:
        cfg = load_workflow(workflow)
    except FileNotFoundError as e:
        raise RuntimeError(f"manual run is not implemented for workflow: {workflow}") from e
    run_now = str(cfg.extra.get("run_now") or "").strip()
    if not run_now:
        raise RuntimeError(f"manual run is not implemented for workflow: {workflow}")
    return load_factory(run_now)(**(inputs or {}))


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

    uvicorn.run("paca.os_app:app", host="127.0.0.1", port=port, reload=reload)


@app.command("dashboard")
def dashboard(
    build: bool = typer.Option(False, "--build", help="Run `pnpm build` instead of dev"),
    start: bool = typer.Option(
        False, "--start", help="Run `pnpm start` (production server, requires prior --build)"
    ),
    port: int = typer.Option(3000, help="Port for the Next.js server"),
) -> None:
    """Run the Next.js dashboard from ``dashboard/``.

    The dashboard is fully decoupled from ``paca serve`` — its server actions
    spawn ``paca`` CLI children directly, and its data layer reads Postgres
    via ``pg``. You only need ``paca serve`` running when something on the
    page actually talks to AgentOS HTTP endpoints (none today).

    This subcommand is a thin wrapper over ``pnpm`` so the operator has a
    single ``paca`` entrypoint.
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
        typer.secho(
            f"dashboard/package.json missing under {cwd}", fg=typer.colors.RED, err=True
        )
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
    name: str = typer.Argument(..., help="Agent name (see `paca list`)"),
    prompt: str = typer.Argument(..., help="Prompt to send to the agent"),
    stream: bool = typer.Option(True, help="Stream response tokens to stdout"),
) -> None:
    """One-shot agent invocation without starting AgentOS."""
    from paca.agents.loader import build_from_name

    agent = build_from_name(name)
    if stream:
        agent.print_response(prompt, stream=True)
    else:
        result = agent.run(prompt)
        typer.echo(result.content if hasattr(result, "content") else str(result))


@app.command("doctor")
def doctor() -> None:
    """Check that the environment is set up enough to run the system."""
    checks: list[tuple[str, bool, str]] = []

    # 1. .env essentials
    db = os.environ.get("DATABASE_URL")
    checks.append(("DATABASE_URL", bool(db), db or "not set"))
    checks.append(
        (
            "ANTHROPIC_API_KEY",
            bool(os.environ.get("ANTHROPIC_API_KEY")),
            "set" if os.environ.get("ANTHROPIC_API_KEY") else "not set (claude_* profiles will fail)",
        )
    )
    checks.append(
        (
            "DEEPSEEK_API_KEY",
            bool(os.environ.get("DEEPSEEK_API_KEY")),
            "set" if os.environ.get("DEEPSEEK_API_KEY") else "not set (local* fallback to deepseek will fail)",
        )
    )

    # 2. OMLX endpoint (env-driven; see paca.core.models.omlx_endpoint)
    omlx_url = os.environ.get("OMLX_BASE_URL")
    checks.append(
        (
            "OMLX_BASE_URL",
            bool(omlx_url),
            omlx_url or "not set (omlx profiles will fail to fallback_profile)",
        )
    )

    # 3. Postgres reachable?
    db_ok = False
    db_msg = "skipped (no DATABASE_URL)"
    if db:
        try:
            import psycopg

            with psycopg.connect(db, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            db_ok = True
            db_msg = "reachable"
        except Exception as e:  # noqa: BLE001
            db_msg = f"unreachable: {e}"
    checks.append(("Postgres", db_ok, db_msg))

    # 4. configs / agents present?
    agents = list_agents()
    checks.append(("configured agents", bool(agents), ", ".join(agents) or "none"))

    # 5. tool registry imports
    from paca import registry

    available = registry.available()
    checks.append(("registered tools", bool(available), f"{len(available)} tools"))

    # 6. GBrain CLI / service health
    checks.append(_check_gbrain())

    # 6b. folocli auth (info-radar collector)
    checks.append(_check_folocli())

    # 6c. info-radar analysis goals.yaml present?
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

    from paca.tools.gbrain import gbrain_search

    typer.echo(json.dumps(gbrain_search.entrypoint(query, limit), ensure_ascii=False, indent=2))


@knowledge_app.command("gbrain-ingest")
def knowledge_gbrain_ingest(
    path: str = typer.Argument(..., help="Markdown file or directory to import."),
) -> None:
    """Import markdown into GBrain through the local CLI bridge."""
    import json

    from paca.tools.gbrain import gbrain_ingest

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
    from paca.integrations.gbrain import _gbrain_bin, gbrain_env, resolve_gbrain_home

    resolved_home = resolve_gbrain_home(str(home))
    db_path = Path(resolved_home) / ".gbrain" / "brain.pglite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [_gbrain_bin(), "init", "--pglite", "--path", str(db_path)],
        check=False,
        capture_output=True,
        env=gbrain_env(paca_home=resolved_home),
        text=True,
        timeout=120,
    )
    if result.stdout.strip():
        typer.echo(result.stdout.strip())
    if result.stderr.strip():
        typer.echo(result.stderr.strip(), err=True)
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)

    typer.echo(f"PACA_GBRAIN_HOME={resolved_home}")
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

    from paca.workflows.knowledge_ingest import ingest_one

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
    from paca.workflows.knowledge_review import run as run_review

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
    the UI; there is no background scheduler.
    """
    import json

    result = _run_workflow_now(name)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@info_radar_app.command("pull")
def info_radar_pull(
    source: str | None = typer.Option(
        None, "--source", help="Pull only this source (default: every enabled source)."
    ),
) -> None:
    """Invoke each enabled source's CLI, parse stdout, and upsert to radar_items."""
    from paca.collectors.info_radar.runner import all_failed, run_all

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
    from paca.collectors.info_radar import store

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
    locale: str = typer.Option(
        "en", "--locale", help="Output language of generated analysis: zh or en."
    ),
) -> None:
    """Run the two-tier analysis pipeline over unseen radar_items."""
    from paca.workflows.info_radar_analysis import run as run_analysis

    if locale not in ("zh", "en"):
        raise typer.BadParameter("--locale must be 'zh' or 'en'")

    counters = run_analysis(limit=limit, source=source, locale=locale)
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
    from paca.workflows.info_radar_recap import run as run_recap

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
            f"info-radar recap: no items cleared the gate for "
            f"{result['since']}..{result['until']}"
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

    from paca.integrations.info_radar.folo import subscription_list

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
