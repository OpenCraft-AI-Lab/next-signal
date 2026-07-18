"""Tests for database_url — env requirement and the psycopg v3 scheme rewrite."""

from __future__ import annotations

import pytest

from paca.core import db as db_mod


def test_database_url_requires_env(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL not set"):
        db_mod.database_url()


def test_database_url_passthrough(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/paca")
    assert db_mod.database_url() == "postgresql://localhost:5432/paca"


def test_database_url_rewrites_scheme_for_sqlalchemy(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/paca")
    assert (
        db_mod.database_url(for_sqlalchemy=True)
        == "postgresql+psycopg://localhost:5432/paca"
    )
