"""Shared dataclasses for info-radar parsers and the runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


@dataclass(frozen=True)
class RadarItem:
    """One parsed item, normalized across sources.

    ``source_id`` + the runner-injected source name form the Postgres unique
    key. ``payload`` keeps the raw upstream record verbatim so future migrations
    or re-parses can recover fields without re-fetching.
    """

    source_id: str
    title: str
    url: str | None
    excerpt: str | None
    published_at: datetime | None
    payload: dict[str, Any]


# Parsers take CLI stdout and the source's YAML name, return RadarItems.
# They MUST NOT touch the database.
ParserFn = Callable[[str, str], list[RadarItem]]
