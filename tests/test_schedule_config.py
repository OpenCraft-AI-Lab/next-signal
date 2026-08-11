"""Schedule file parsing and slot arithmetic. No DB, no ambient clock."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from next_signal.core import schedule as sched

TZ = ZoneInfo("America/Los_Angeles")


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "schedule.json"
    monkeypatch.setattr(sched, "SCHEDULE_STATE_FILE", path)
    return path


# --- prev_slot -------------------------------------------------------------


def test_slot_earlier_the_same_day():
    now = datetime(2026, 8, 9, 14, 30, tzinfo=TZ)
    assert sched.prev_slot("08:00", now) == datetime(2026, 8, 9, 8, 0, tzinfo=TZ)


def test_before_the_time_falls_back_to_yesterday():
    now = datetime(2026, 8, 9, 6, 0, tzinfo=TZ)
    assert sched.prev_slot("08:00", now) == datetime(2026, 8, 8, 8, 0, tzinfo=TZ)


def test_exactly_on_the_slot_counts_as_reached():
    now = datetime(2026, 8, 9, 8, 0, tzinfo=TZ)
    assert sched.prev_slot("08:00", now) == now


def test_seconds_are_truncated():
    now = datetime(2026, 8, 9, 8, 0, 47, 500, tzinfo=TZ)
    assert sched.prev_slot("08:00", now) == datetime(2026, 8, 9, 8, 0, tzinfo=TZ)


def test_spring_forward_gap_stays_defined():
    """02:30 does not exist on the US spring-forward day; we only require a
    defined, stable, not-in-the-future answer — see design.md D3."""
    now = datetime(2026, 3, 8, 10, 0, tzinfo=TZ)
    slot = sched.prev_slot("02:30", now)
    assert slot <= now
    assert slot == sched.prev_slot("02:30", now)


def test_fall_back_repeat_hour_stays_defined():
    now = datetime(2026, 11, 1, 10, 0, tzinfo=TZ)
    slot = sched.prev_slot("01:30", now)
    assert slot <= now
    assert slot == sched.prev_slot("01:30", now)


# --- several daily times ---------------------------------------------------


def test_picks_the_latest_time_already_passed():
    now = datetime(2026, 8, 9, 14, 0, tzinfo=TZ)
    slot = sched.prev_slot(("08:00", "13:00", "20:00"), now)
    assert slot == datetime(2026, 8, 9, 13, 0, tzinfo=TZ)


def test_before_the_first_time_falls_back_to_yesterdays_last():
    now = datetime(2026, 8, 9, 6, 0, tzinfo=TZ)
    slot = sched.prev_slot(("08:00", "13:00", "20:00"), now)
    assert slot == datetime(2026, 8, 8, 20, 0, tzinfo=TZ)


def test_after_the_last_time_uses_it():
    now = datetime(2026, 8, 9, 23, 30, tzinfo=TZ)
    slot = sched.prev_slot(("08:00", "13:00", "20:00"), now)
    assert slot == datetime(2026, 8, 9, 20, 0, tzinfo=TZ)


def test_order_of_the_times_does_not_matter():
    now = datetime(2026, 8, 9, 14, 0, tzinfo=TZ)
    assert sched.prev_slot(("20:00", "08:00", "13:00"), now) == sched.prev_slot(
        ("08:00", "13:00", "20:00"), now
    )


def test_one_time_behaves_exactly_as_before():
    now = datetime(2026, 8, 9, 14, 30, tzinfo=TZ)
    assert sched.prev_slot(("08:00",), now) == sched.prev_slot("08:00", now)


def test_no_times_raises():
    with pytest.raises(RuntimeError, match="at least one time"):
        sched.prev_slot((), datetime(2026, 8, 9, 14, 0, tzinfo=TZ))


# --- load_schedule ---------------------------------------------------------


def test_absent_file_reads_as_disabled(state_file):
    cfg = sched.load_schedule()
    assert cfg == sched.Schedule(enabled=False, at=(), catch_up=False)
    assert not state_file.exists(), "reading must not create the file"


def test_configured_file_round_trips(state_file):
    state_file.write_text(
        json.dumps({"enabled": True, "at": ["08:00", "20:00"], "catch_up": True})
    )
    assert sched.load_schedule() == sched.Schedule(
        enabled=True, at=("08:00", "20:00"), catch_up=True
    )


def test_a_bare_string_still_reads(state_file):
    """Files written before multiple daily runs existed hold a single string."""
    state_file.write_text(json.dumps({"enabled": True, "at": "08:00"}))
    assert sched.load_schedule().at == ("08:00",)


def test_times_are_deduped_and_sorted(state_file):
    state_file.write_text(
        json.dumps({"enabled": True, "at": ["20:00", "08:00", "20:00", " 13:30 "]})
    )
    assert sched.load_schedule().at == ("08:00", "13:30", "20:00")


def test_blank_entries_are_dropped(state_file):
    state_file.write_text(json.dumps({"enabled": True, "at": ["08:00", "", "  "]}))
    assert sched.load_schedule().at == ("08:00",)


def test_one_bad_time_in_the_list_raises(state_file):
    state_file.write_text(json.dumps({"enabled": True, "at": ["08:00", "25:00"]}))
    with pytest.raises(RuntimeError, match="25:00"):
        sched.load_schedule()


def test_enabled_with_an_empty_list_raises(state_file):
    state_file.write_text(json.dumps({"enabled": True, "at": []}))
    with pytest.raises(RuntimeError, match="required when enabled"):
        sched.load_schedule()


def test_at_of_the_wrong_shape_raises(state_file):
    state_file.write_text(json.dumps({"enabled": False, "at": {"h": 8}}))
    with pytest.raises(RuntimeError, match="string or a list"):
        sched.load_schedule()


def test_catch_up_defaults_off(state_file):
    state_file.write_text(json.dumps({"enabled": True, "at": "08:00"}))
    assert sched.load_schedule().catch_up is False


def test_corrupt_json_raises(state_file):
    state_file.write_text("{not json")
    with pytest.raises(RuntimeError, match="corrupt"):
        sched.load_schedule()


def test_non_object_raises(state_file):
    state_file.write_text("[]")
    with pytest.raises(RuntimeError, match="must be an object"):
        sched.load_schedule()


@pytest.mark.parametrize("bad", ["25:00", "08:60", "8am", "0800", "", "08:00:00"])
def test_invalid_times_raise_when_enabled(state_file, bad):
    state_file.write_text(json.dumps({"enabled": True, "at": bad}))
    with pytest.raises(RuntimeError):
        sched.load_schedule()


def test_invalid_time_raises_even_while_disabled(state_file):
    state_file.write_text(json.dumps({"enabled": False, "at": "25:00"}))
    with pytest.raises(RuntimeError, match="25:00"):
        sched.load_schedule()


def test_disabled_without_a_time_is_fine(state_file):
    state_file.write_text(json.dumps({"enabled": False}))
    assert sched.load_schedule().enabled is False


def test_a_quoted_false_does_not_switch_the_schedule_on(state_file):
    """`bool("false")` is `True`, and this file is edited by hand.

    That one coercion turns an operator switching the schedule off into a
    scheduler that stays on — on the only path in the system that spends model
    tokens with nobody watching.
    """
    state_file.write_text(json.dumps({"enabled": "false", "at": "08:00"}))
    with pytest.raises(RuntimeError, match="must be true or false"):
        sched.load_schedule()


@pytest.mark.parametrize("key", ["enabled", "catch_up"])
@pytest.mark.parametrize("bad", ["true", "yes", 1, 0, None, [], {}])
def test_a_flag_that_is_not_a_boolean_raises(state_file, key, bad):
    state_file.write_text(json.dumps({"enabled": True, "at": "08:00", key: bad}))
    with pytest.raises(RuntimeError, match=f"`{key}` must be true or false"):
        sched.load_schedule()
