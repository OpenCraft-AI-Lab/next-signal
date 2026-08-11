"""Local wall-clock helpers: one day boundary shared by every surface.

Radar day grouping, review due dates, and the scheduler all have to agree on
what "today" and "08:00" mean, or a scheduled run lands on a different day than
the one it shows up under. They agree by all reading ``INFO_RADAR_TIMEZONE``
through here.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

# Matches dashboard/lib/radar/queries.ts so the dashboard and the pipeline
# bucket the same rows into the same day.
_DEFAULT_TZ = "America/Los_Angeles"


def radar_timezone() -> str:
    """Local timezone for day boundaries. Read at call time, not at import."""
    return os.environ.get("INFO_RADAR_TIMEZONE", "").strip() or _DEFAULT_TZ


def now_local() -> datetime:
    """Now, timezone-aware, in the radar timezone."""
    return datetime.now(ZoneInfo(radar_timezone()))


def today_local() -> date:
    """Today in the radar timezone — the same 'today' the dashboard uses."""
    return now_local().date()
