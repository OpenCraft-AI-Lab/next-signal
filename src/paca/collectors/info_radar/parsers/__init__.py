"""Parser registry. Each source's YAML ``parser:`` references a name here.

Unknown names fail fast at config load time (see ``loader.py``). Add a new
source by writing a parser function and registering it below.
"""

from __future__ import annotations

from paca.collectors.info_radar.parsers.folo import folo_timeline
from paca.collectors.info_radar.schema import ParserFn

PARSERS: dict[str, ParserFn] = {
    "folo_timeline": folo_timeline,
}

__all__ = ["PARSERS"]
