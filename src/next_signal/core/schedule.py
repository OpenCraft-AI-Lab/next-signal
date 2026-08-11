"""The unattended run schedule: a state file the dashboard writes and the scheduler reads.

Lives in the state root rather than ``configs/`` because the dashboard writes
it and the repo tree inside the container is image-baked. Same posture as
``core.language``'s preference file: read at call time so a dashboard edit takes
effect without a restart, loud on a malformed file, and silent about an absent
one — nobody has configured a schedule yet is a valid, permanent state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from next_signal.core.paths import STATE_ROOT

SCHEDULE_STATE_FILE = STATE_ROOT / "schedule.json"


@dataclass(frozen=True)
class Schedule:
    """When the radar chain runs unattended, and what to do about missed runs."""

    enabled: bool
    # Wall-clock "HH:MM" times in the radar timezone, sorted and deduplicated;
    # empty when never configured. The set is a *daily* pattern — every listed
    # time fires every day.
    at: tuple[str, ...]
    catch_up: bool


_DISABLED = Schedule(enabled=False, at=(), catch_up=False)


def parse_at(at: str) -> tuple[int, int]:
    """Split a ``HH:MM`` wall-clock time into (hour, minute)."""
    parts = at.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise RuntimeError(f"invalid schedule time {at!r}; expected HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise RuntimeError(f"invalid schedule time {at!r}; expected 00:00-23:59")
    return hour, minute


def load_schedule() -> Schedule:
    """Read the schedule. Absent file → disabled; malformed file → ``RuntimeError``."""
    if not SCHEDULE_STATE_FILE.exists():
        return _DISABLED
    try:
        data = json.loads(SCHEDULE_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{SCHEDULE_STATE_FILE} is corrupt: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{SCHEDULE_STATE_FILE}: top-level must be an object")

    enabled = _read_flag(data, "enabled")
    at = _read_times(data.get("at"))
    if enabled and not at:
        raise RuntimeError(f"{SCHEDULE_STATE_FILE}: `at` is required when enabled")
    return Schedule(enabled=enabled, at=at, catch_up=_read_flag(data, "catch_up"))


def _read_flag(data: dict, key: str) -> bool:
    """Read a boolean field. Absent is false; a present non-boolean is fatal.

    `bool("false")` is `True`, and this file is hand-editable by design — that
    one coercion turns an operator switching the schedule off into a scheduler
    that stays on, on the only path in the system that spends model tokens with
    nobody watching. Same posture as ``_read_times`` next door, which validates a
    time even while the schedule is disabled.
    """
    value = data.get(key, False)
    if not isinstance(value, bool):
        raise RuntimeError(
            f"{SCHEDULE_STATE_FILE}: `{key}` must be true or false, not {value!r}"
        )
    return value


def _read_times(raw: object) -> tuple[str, ...]:
    """Normalize the `at` field to sorted, deduplicated ``HH:MM`` times.

    Accepts a bare string as well as a list: the field held a single time before
    multiple daily runs existed, and a file written by that version is still on
    disk. Reading one is a migration, not a fallback — the next dashboard write
    stores a list.
    """
    if raw is None:
        return ()
    values = [raw] if isinstance(raw, str) else raw
    if not isinstance(values, list):
        raise RuntimeError(f"{SCHEDULE_STATE_FILE}: `at` must be a string or a list")
    times = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        parse_at(text)  # validate even while disabled — a bad value is a bad value
        times.add(text)
    return tuple(sorted(times))


def prev_slot(at: tuple[str, ...] | str, now: datetime) -> datetime:
    """The most recent occurrence of any time in ``at``, at or before ``now``.

    With several daily times the answer is just the latest of the per-time
    candidates, which is why nothing downstream had to change: due-ness stays
    "is the current slot newer than the one already handled?".

    ``timedelta`` arithmetic on an aware datetime is wall-clock arithmetic, so
    "yesterday at 08:00" stays 08:00 across a DST boundary. On the one
    spring-forward day where a configured time does not exist, fold resolution
    yields a defined instant up to an hour off and the next day corrects it.
    """
    times = (at,) if isinstance(at, str) else tuple(at)
    if not times:
        raise RuntimeError("prev_slot needs at least one time")
    return max(_slot_for(t, now) for t in times)


def _slot_for(at: str, now: datetime) -> datetime:
    hour, minute = parse_at(at)
    slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return slot if slot <= now else slot - timedelta(days=1)
