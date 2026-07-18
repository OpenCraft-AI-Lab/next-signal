"""Single Postgres + pgvector connection used by AgentOS and our own tables.

The database URL is read from ``DATABASE_URL`` env var. agno's PostgresDb will
auto-provision its own tables (sessions, memory, knowledge, traces). We add
``job_runs`` and ``scheduled_jobs`` in ``scripts/bootstrap_db.py``.
"""

from __future__ import annotations

import os
from functools import lru_cache

from agno.db.postgres import PostgresDb


def database_url(*, for_sqlalchemy: bool = False) -> str:
    """Return DATABASE_URL.

    SQLAlchemy's default driver for ``postgresql://`` is ``psycopg2``; we use
    ``psycopg`` (v3) instead. When ``for_sqlalchemy=True`` we rewrite the
    scheme to ``postgresql+psycopg://`` so SQLAlchemy picks the right driver
    while users keep a normal Postgres URL in their .env.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. Example: "
            "postgresql://localhost:5432/intelligent_digitalpaca"
        )
    if for_sqlalchemy and url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@lru_cache(maxsize=1)
def get_db() -> PostgresDb:
    """Return a process-wide singleton PostgresDb instance."""
    return PostgresDb(db_url=database_url(for_sqlalchemy=True))
