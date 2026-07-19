"""Structured logging via structlog. Console-pretty in dev, JSON for non-TTY runs."""

from __future__ import annotations

import logging
import os
import sys

import structlog


def configure(json_logs: bool | None = None, level: str = "INFO") -> None:
    """Configure structlog. Call once at process startup.

    json_logs: force JSON output. Defaults to True when stdout is not a TTY
    (so dashboard-spawned / redirected CLI runs produce parseable logs).
    """
    if json_logs is None:
        json_logs = not sys.stdout.isatty()

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
    ]

    if json_logs:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        cache_logger_on_first_use=True,
    )

    # Tame noisy stdlib loggers; agno + httpx default to INFO.
    logging.basicConfig(
        level=os.environ.get("PACA_LOG_LEVEL", "INFO"),
        format="%(message)s",
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
