"""Scheduler seeding, due-ness, and chain behavior against a real Postgres.

Skipped without DATABASE_URL. Each test claims a unique job name so a run never
touches the production `radar` row, and cleans it up afterwards. Only the two
boundaries are substituted — the wall clock and `run_workflow_now` — so the
seeding rules and the slot comparison run for real against real rows.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")
import psycopg  # noqa: E402

from next_signal.core.schedule import Schedule  # noqa: E402
from next_signal.orchestrator import schedule as orch  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set; skipping scheduler integration tests",
)

TZ = ZoneInfo("America/Los_Angeles")
NOON = datetime(2026, 8, 9, 12, 0, tzinfo=TZ)
EIGHT_AM = datetime(2026, 8, 9, 8, 0, tzinfo=TZ)

ON = Schedule(enabled=True, at=("08:00",), catch_up=False)
ON_CATCH_UP = Schedule(enabled=True, at=("08:00",), catch_up=True)
OFF = Schedule(enabled=False, at=(), catch_up=False)


def _has_table(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM schedule_state LIMIT 1")
            cur.fetchone()
        return True
    except Exception:
        return False


if DATABASE_URL and not _has_table(DATABASE_URL):
    pytest.skip(
        "schedule_state table missing; run `uv run python scripts/bootstrap_db.py`",
        allow_module_level=True,
    )


@pytest.fixture
def job(monkeypatch):
    """A throwaway job name, substituted for the module-level `radar`."""
    name = f"test-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(orch, "JOB", name)
    yield name
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM schedule_state WHERE job = %s", (name,))


@pytest.fixture
def clock(monkeypatch):
    """Pin the scheduler's wall clock; returns a setter."""

    def at(moment: datetime) -> None:
        monkeypatch.setattr(orch, "now_local", lambda: moment)

    at(NOON)
    return at


@pytest.fixture
def fired(monkeypatch):
    """Record chain invocations instead of running workflows."""
    calls: list[str] = []
    monkeypatch.setattr(orch, "fire", lambda job: calls.append(job))
    return calls


def _tick(monkeypatch, cfg, *, last_effective=None, tick_seconds=orch.TICK_SECONDS):
    monkeypatch.setattr(orch, "load_schedule", lambda: cfg)
    return orch.tick(last_effective, tick_seconds=tick_seconds)


def _row(job: str) -> dict:
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT last_slot_at, last_run_at, last_status, last_error "
            "FROM schedule_state WHERE job = %s",
            (job,),
        )
        row = cur.fetchone()
    if row is None:
        return {}
    return dict(zip(("last_slot_at", "last_run_at", "last_status", "last_error"), row))


# --- seeding ---------------------------------------------------------------


def test_first_sight_seeds_without_running(job, clock, fired, monkeypatch):
    _tick(monkeypatch, ON)
    assert fired == []
    assert _row(job)["last_slot_at"] == EIGHT_AM


def test_first_sight_seeds_even_with_catch_up(job, clock, fired, monkeypatch):
    """catch_up means "a run was missed", not "there is no history"."""
    _tick(monkeypatch, ON_CATCH_UP)
    assert fired == []
    assert _row(job)["last_slot_at"] == EIGHT_AM


def test_a_slot_that_just_came_due_fires_without_catch_up(job, clock, fired, monkeypatch):
    """Within a poll or two of the slot nothing was missed, so catch_up has no say."""
    orch.write_slot(job, EIGHT_AM - timedelta(days=1))
    clock(EIGHT_AM + timedelta(seconds=20))
    _tick(monkeypatch, ON)
    assert fired == [job]


def test_missed_slot_without_catch_up_is_seeded(job, clock, fired, monkeypatch):
    orch.write_slot(job, EIGHT_AM - timedelta(days=3))
    _tick(monkeypatch, ON)  # clock is at noon: four hours past the slot
    assert fired == []
    assert _row(job)["last_slot_at"] == EIGHT_AM


def test_missed_slot_with_catch_up_runs(job, clock, fired, monkeypatch):
    orch.write_slot(job, EIGHT_AM - timedelta(days=1))
    _tick(monkeypatch, ON_CATCH_UP)
    assert fired == [job]
    assert _row(job)["last_slot_at"] == EIGHT_AM


def test_several_missed_days_collapse_into_one_run(job, clock, fired, monkeypatch):
    orch.write_slot(job, EIGHT_AM - timedelta(days=5))
    _tick(monkeypatch, ON_CATCH_UP)
    assert fired == [job], "one run, not one per missed day"


def test_a_host_suspended_across_the_slot_honours_catch_up(job, clock, fired, monkeypatch):
    """The case a process-start rule gets wrong: two ticks, one live process, and
    the slot goes by between them because the laptop was asleep."""
    clock(datetime(2026, 8, 9, 7, 0, tzinfo=TZ))
    effective = _tick(monkeypatch, ON)  # seeds yesterday's 08:00
    clock(datetime(2026, 8, 9, 9, 30, tzinfo=TZ))  # woke up past today's
    _tick(monkeypatch, ON, last_effective=effective)
    assert fired == []
    assert _row(job)["last_slot_at"] == EIGHT_AM


def test_a_run_that_overruns_the_next_time_does_not_stack(job, clock, fired, monkeypatch):
    """08:00 is still executing at 09:20, so nobody was watching 09:00."""
    hourly = Schedule(enabled=True, at=("08:00", "09:00"), catch_up=False)
    orch.write_slot(job, EIGHT_AM)  # written by the 08:00 run before it fired
    clock(datetime(2026, 8, 9, 9, 20, tzinfo=TZ))
    _tick(monkeypatch, hourly, last_effective=(True, hourly.at))
    assert fired == []
    assert _row(job)["last_slot_at"] == datetime(2026, 8, 9, 9, 0, tzinfo=TZ)


def test_changing_the_time_does_not_fire_the_slot_that_just_passed(job, clock, fired, monkeypatch):
    _tick(monkeypatch, ON)
    moved = Schedule(enabled=True, at=("11:00",), catch_up=True)
    _tick(monkeypatch, moved, last_effective=(True, ("08:00",)))
    assert fired == []
    assert _row(job)["last_slot_at"] == datetime(2026, 8, 9, 11, 0, tzinfo=TZ)


def test_enabling_does_not_fire_a_backlog(job, clock, fired, monkeypatch):
    orch.write_slot(job, EIGHT_AM - timedelta(days=2))
    _tick(monkeypatch, ON_CATCH_UP, last_effective=(False, ()))
    assert fired == []
    assert _row(job)["last_slot_at"] == EIGHT_AM


# --- due-ness --------------------------------------------------------------


def test_slot_reached_while_running_fires(job, clock, fired, monkeypatch):
    effective = _tick(monkeypatch, ON)  # seeds 08:00
    clock(datetime(2026, 8, 10, 8, 0, tzinfo=TZ))  # next day's slot arrives
    _tick(monkeypatch, ON, last_effective=effective)
    assert fired == [job]


def test_completed_slot_does_not_refire(job, clock, fired, monkeypatch):
    effective = _tick(monkeypatch, ON)
    clock(datetime(2026, 8, 9, 14, 0, tzinfo=TZ))
    _tick(monkeypatch, ON, last_effective=effective)
    assert fired == []


def test_restart_after_a_run_does_not_replay(job, clock, fired, monkeypatch):
    orch.write_slot(job, EIGHT_AM)  # the slot is already handled
    _tick(monkeypatch, ON_CATCH_UP)
    assert fired == []


def test_disabled_does_nothing_at_all(job, clock, fired, monkeypatch):
    _tick(monkeypatch, OFF)
    assert fired == []
    assert _row(job) == {}, "a disabled schedule must not create state"


# --- several daily times ---------------------------------------------------

THRICE = Schedule(enabled=True, at=("08:00", "13:00", "20:00"), catch_up=False)


def test_every_daily_time_fires_in_turn(job, clock, fired, monkeypatch):
    effective = _tick(monkeypatch, THRICE)  # seeds 08:00
    assert fired == []

    clock(datetime(2026, 8, 9, 13, 0, tzinfo=TZ))
    _tick(monkeypatch, THRICE, last_effective=effective)
    assert fired == [job]
    assert _row(job)["last_slot_at"] == datetime(2026, 8, 9, 13, 0, tzinfo=TZ)

    clock(datetime(2026, 8, 9, 20, 0, tzinfo=TZ))
    _tick(monkeypatch, THRICE, last_effective=effective)
    assert fired == [job, job], "each configured time is its own run"
    assert _row(job)["last_slot_at"] == datetime(2026, 8, 9, 20, 0, tzinfo=TZ)


def test_between_two_times_nothing_fires(job, clock, fired, monkeypatch):
    effective = _tick(monkeypatch, THRICE)  # seeds 08:00
    clock(datetime(2026, 8, 9, 12, 59, tzinfo=TZ))
    _tick(monkeypatch, THRICE, last_effective=effective)
    assert fired == []


def test_many_missed_times_still_collapse_to_one_run(job, clock, fired, monkeypatch):
    """Down for two days across three daily times is six missed slots — but
    catching up means "resume", not "replay six runs"."""
    catch_up = Schedule(enabled=True, at=THRICE.at, catch_up=True)
    orch.write_slot(job, datetime(2026, 8, 7, 8, 0, tzinfo=TZ))
    _tick(monkeypatch, catch_up)
    assert fired == [job]
    assert _row(job)["last_slot_at"] == datetime(2026, 8, 9, 8, 0, tzinfo=TZ)


def test_adding_a_time_does_not_fire_the_one_just_passed(job, clock, fired, monkeypatch):
    """Adding 11:00 at noon must not immediately fire this morning's 11:00."""
    effective = _tick(monkeypatch, ON)  # 08:00 only, seeds 08:00
    widened = Schedule(enabled=True, at=("08:00", "11:00"), catch_up=True)
    _tick(monkeypatch, widened, last_effective=effective)
    assert fired == []
    assert _row(job)["last_slot_at"] == datetime(2026, 8, 9, 11, 0, tzinfo=TZ)


# --- the chain -------------------------------------------------------------


def test_successful_chain_runs_both_stages_in_order(job, monkeypatch):
    orch.claim_slot(job, EIGHT_AM)  # tick always claims the slot before firing
    calls: list[str] = []
    monkeypatch.setattr(orch, "run_workflow_now", lambda w: calls.append(w) or {})
    orch.fire(job)
    assert calls == ["info_radar_pull", "info_radar_analysis"]
    row = _row(job)
    assert row["last_status"] == "ok"
    assert row["last_error"] is None
    assert row["last_run_at"] is not None


def test_failed_stage_stops_the_chain_and_names_itself(job, monkeypatch):
    orch.claim_slot(job, EIGHT_AM)
    calls: list[str] = []

    def boom(workflow: str) -> dict:
        calls.append(workflow)
        raise RuntimeError("source unreachable")

    monkeypatch.setattr(orch, "run_workflow_now", boom)
    orch.fire(job)  # must not propagate
    assert calls == ["info_radar_pull"], "analysis must not run after a failed pull"
    row = _row(job)
    assert row["last_status"] == "failed"
    assert "info_radar_pull" in row["last_error"]
    assert "source unreachable" in row["last_error"]


def test_success_clears_a_previous_error(job, monkeypatch):
    orch.write_slot(job, EIGHT_AM)
    orch.write_run_state(job, status="failed", error="info_radar_pull: boom")
    orch.claim_slot(job, EIGHT_AM)
    monkeypatch.setattr(orch, "run_workflow_now", lambda w: {})
    orch.fire(job)
    row = _row(job)
    assert row["last_status"] == "ok"
    assert row["last_error"] is None


def test_a_run_is_visible_while_it_runs(job, monkeypatch):
    orch.claim_slot(job, EIGHT_AM)
    seen: list[tuple] = []

    def observe(workflow: str) -> dict:
        row = _row(job)
        seen.append((row["last_status"], row["last_run_at"]))
        return {}

    monkeypatch.setattr(orch, "run_workflow_now", observe)
    orch.fire(job)
    assert [status for status, _ in seen] == ["running", "running"]
    assert seen[0][1] == seen[1][1], "the start is recorded once per chain, not per leg"
    assert _row(job)["last_status"] == "ok"


def test_claiming_a_slot_records_the_run_in_the_same_write(job, monkeypatch):
    """A consumed slot always carries a run, so no run can go missing unseen.

    Split across two writes, the gap between them leaves the slot advanced with
    nothing recorded — a state `reconcile` cannot find (there is no `running`
    row) and the panel cannot show (it still reads the previous run). The day's
    run is simply skipped, silently.
    """
    orch.write_slot(job, EIGHT_AM - timedelta(days=1))
    orch.write_run_state(job, status="ok", error=None)
    monkeypatch.setattr(orch, "fire", lambda job: None)  # died before the chain began

    orch.claim_slot(job, EIGHT_AM)

    row = _row(job)
    assert row["last_slot_at"] == EIGHT_AM, "the slot is consumed"
    assert row["last_status"] == "running", "and the run it belongs to is on record"
    assert row["last_error"] is None, "a fresh run does not inherit an old error"
    # The pairing is what makes the loss recoverable: startup reconciliation now
    # has something to correct rather than a yesterday-shaped silence.
    orch.reconcile(job)
    assert _row(job)["last_status"] == "failed"


# --- interrupted runs ------------------------------------------------------


def test_a_run_left_running_is_reconciled_at_startup(job):
    orch.write_slot(job, EIGHT_AM)
    orch.write_run_state(job, status="running", error=None)
    started = _row(job)["last_run_at"]
    orch.reconcile(job)
    row = _row(job)
    assert row["last_status"] == "failed", "a run nobody finished did not succeed"
    assert row["last_run_at"] == started, "the start instant is all there is to keep"
    assert row["last_error"], "the error line is what says how it failed"


@pytest.mark.parametrize("status", ["ok", "failed"])
def test_reconciliation_leaves_a_finished_run_alone(job, status):
    orch.write_slot(job, EIGHT_AM)
    orch.write_run_state(job, status=status, error="boom" if status == "failed" else None)
    before = _row(job)
    orch.reconcile(job)
    assert _row(job) == before
