"""Wall-clock scheduler: one poll loop, one job, durable slot state.

Everything awkward about scheduling on a laptop — host sleep, container
restarts, Docker being quit for a weekend — collapses into one comparison: is
the most recent scheduled slot newer than the last slot we handled? That is
re-asked from the wall clock and Postgres on every tick, so no case needs its
own code path, and a suspended VM is just an unusually long tick whose slot the
clock then reports as late.

A malformed schedule file propagates out of the loop rather than being caught.
Only a hand-edit can produce one (the dashboard writes validated JSON), and a
container visibly restarting is a louder signal than an error line every 30
seconds; the dashboard stays up either way, so the fix path is unaffected.
"""

from __future__ import annotations

import time
from datetime import datetime

import psycopg

from next_signal.core.clock import now_local, radar_timezone
from next_signal.core.db import database_url
from next_signal.core.logging import get_logger
from next_signal.core.schedule import load_schedule, prev_slot
from next_signal.orchestrator.run_now import run_workflow_now

log = get_logger(__name__)

JOB = "radar"
CHAIN = ("info_radar_pull", "info_radar_analysis")
TICK_SECONDS = 30


def read_slot(job: str) -> datetime | None:
    """The last slot handled for ``job``, or ``None`` if it has never been seen."""
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_slot_at FROM schedule_state WHERE job = %s", (job,))
            row = cur.fetchone()
    return row[0] if row else None


def write_slot(job: str, slot: datetime) -> None:
    """Record ``slot`` as handled without running it — seeding only.

    Firing a slot goes through ``claim_slot`` instead, which also records that
    the run began.
    """
    sql = """
        INSERT INTO schedule_state (job, last_slot_at) VALUES (%s, %s)
        ON CONFLICT (job) DO UPDATE SET last_slot_at = EXCLUDED.last_slot_at
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (job, slot))
        conn.commit()


def claim_slot(job: str, slot: datetime) -> None:
    """Consume ``slot`` and mark the run started, in one statement.

    Consuming a slot and beginning a run are one decision, so they are one write.
    Split across two connections, the gap between them can leave the slot
    advanced with no run recorded — and that state is invisible afterwards:
    ``reconcile`` has no ``running`` row to correct, so the panel goes on showing
    the previous run while the day's run has silently been skipped.
    """
    sql = """
        INSERT INTO schedule_state (job, last_slot_at, last_run_at, last_status, last_error)
        VALUES (%s, %s, now(), 'running', NULL)
        ON CONFLICT (job) DO UPDATE SET
            last_slot_at = EXCLUDED.last_slot_at,
            last_run_at = EXCLUDED.last_run_at,
            last_status = EXCLUDED.last_status,
            last_error = EXCLUDED.last_error
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (job, slot))
        conn.commit()


def write_run_state(job: str, *, status: str, error: str | None) -> None:
    """Record where the most recent run stands — that it started, then how it ended.

    ``last_run_at`` therefore carries the start instant for the length of the run
    and the finish instant afterwards, which is what lets the dashboard tell a
    long run apart from no run at all.
    """
    sql = """
        UPDATE schedule_state
           SET last_run_at = now(), last_status = %s, last_error = %s
         WHERE job = %s
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (status, error[:2000] if error else None, job))
        conn.commit()


def reconcile(job: str = JOB) -> None:
    """Record a run left in progress by a dead process as failed.

    Startup is the only place this is needed: the poll loop runs jobs inline on
    one thread, so a ``running`` row seen by the process that wrote it really is
    running. Keeps ``last_run_at`` — the instant the lost run started. The error
    line is what says *how* it failed; the row is overwritten by the next run, so
    a status of its own could never be counted over time.
    """
    sql = """
        UPDATE schedule_state
           SET last_status = 'failed', last_error = %s
         WHERE job = %s AND last_status = 'running'
    """
    reason = "the scheduler exited before this run finished"
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (reason, job))
            found = cur.rowcount
        conn.commit()
    if found:
        log.warning("schedule_run_interrupted", job=job)


def fire(job: str = JOB) -> None:
    """Run the chain in order, stopping at the first failure. Never raises.

    The run is already marked ``running`` by ``claim_slot``, once per chain
    rather than per leg: the question a reader has is whether the radar is
    running, not which leg it is inside — the legs are already in the log, and a
    chain can run for an hour.
    """
    for workflow in CHAIN:
        log.info("schedule_run_start", job=job, workflow=workflow)
        started = time.monotonic()
        try:
            summary = run_workflow_now(workflow)
        except Exception as e:  # noqa: BLE001
            log.error(
                "schedule_run_failed",
                job=job,
                workflow=workflow,
                seconds=round(time.monotonic() - started, 1),
                error=str(e),
            )
            write_run_state(job, status="failed", error=f"{workflow}: {e}")
            return
        # `summary` is the workflow's own run summary — counters for the
        # analysis pipeline, source tallies for the pull. Logging it here is
        # the only place an unattended run's shape is recorded at all.
        log.info(
            "schedule_run_done",
            job=job,
            workflow=workflow,
            seconds=round(time.monotonic() - started, 1),
            summary=summary,
        )
    write_run_state(job, status="ok", error=None)


Effective = tuple[bool, tuple[str, ...]]


def tick(last_effective: Effective | None, *, tick_seconds: int) -> Effective:
    """Run one poll. Returns the effective schedule, for the next tick to compare against.

    Seeding — recording the current slot as handled *without* running it — happens
    for three reasons, all of which mean "there is no missed run here to honour":
    the job has never been seen, the schedule just changed, or the due slot was
    missed and catch-up is off. Only ``catch_up`` distinguishes the third; a
    changed schedule never fires a slot that has just gone by.
    """
    cfg = load_schedule()
    effective = (cfg.enabled, cfg.at)
    if not cfg.enabled:
        return effective

    now = now_local()
    slot = prev_slot(cfg.at, now)
    stored = read_slot(JOB)
    schedule_changed = last_effective is not None and effective != last_effective
    # Missed = came due while nobody was watching, judged by the clock rather
    # than by process age: the process usually survives the suspend that made us
    # miss it. Two intervals is grace, not precision.
    missed = (
        stored is not None
        and stored < slot
        and (now - slot).total_seconds() > 2 * tick_seconds
    )

    if stored is None or schedule_changed or (missed and not cfg.catch_up):
        write_slot(JOB, slot)
        log.info("schedule_seeded", job=JOB, slot=slot.isoformat(), missed=missed)
        return effective

    if stored < slot:
        # Advance before running: a process killed mid-chain must not replay the
        # slot, because re-running `info_radar_analysis` spends model tokens.
        claim_slot(JOB, slot)
        fire(JOB)
    return effective


def run(tick_seconds: int = TICK_SECONDS) -> None:
    """Poll until interrupted, firing the chain when a slot comes due."""
    # Before reading the schedule, not after: a malformed file raises here and
    # the container restarts into the same raise, so a run left in progress by
    # the previous process would otherwise be reported as still running for as
    # long as the file stays broken — the exact lie this reconciliation exists
    # to prevent. Reconciling needs no configuration.
    reconcile(JOB)
    cfg = load_schedule()
    log.info(
        "schedule_started",
        timezone=radar_timezone(),
        enabled=cfg.enabled,
        at=list(cfg.at) or None,
        catch_up=cfg.catch_up,
        tick_seconds=tick_seconds,
    )
    last_effective: Effective | None = None
    while True:
        last_effective = tick(last_effective, tick_seconds=tick_seconds)
        time.sleep(tick_seconds)
