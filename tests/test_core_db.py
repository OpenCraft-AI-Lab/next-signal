"""Tests for database_url and the business-table schema contract."""

from __future__ import annotations

import pytest

from paca.core import db as db_mod


class _FakeCursor:
    """Stands in for a psycopg cursor over information_schema.columns."""

    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.sql = sql

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)


def _rows_from(contract, *, drop: dict[str, set[str]] | None = None):
    """Live rows that satisfy the contract, minus any columns in `drop`."""
    drop = drop or {}
    return [
        (table, column)
        for table, columns in contract.items()
        for column in columns
        if column not in drop.get(table, set())
    ]


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


def test_schema_contract_satisfied_reports_nothing() -> None:
    conn = _FakeConn(_rows_from(db_mod.BUSINESS_TABLE_COLUMNS))
    assert db_mod.missing_business_columns(conn) == {}


def test_schema_contract_extra_live_columns_are_fine() -> None:
    """Subset test: a column the DDL adds but the contract omits is not a gap."""
    rows = _rows_from(db_mod.BUSINESS_TABLE_COLUMNS) + [("radar_items", "brand_new_col")]
    assert db_mod.missing_business_columns(_FakeConn(rows)) == {}


def test_schema_contract_reports_the_missing_column() -> None:
    """The real regression: `radar_analyses.title` shipped but never migrated."""
    rows = _rows_from(db_mod.BUSINESS_TABLE_COLUMNS, drop={"radar_analyses": {"title"}})
    assert db_mod.missing_business_columns(_FakeConn(rows)) == {"radar_analyses": ["title"]}


def test_schema_contract_reports_a_wholly_absent_table() -> None:
    rows = [
        (t, c)
        for t, c in _rows_from(db_mod.BUSINESS_TABLE_COLUMNS)
        if t != "knowledge_reviews"
    ]
    gaps = db_mod.missing_business_columns(_FakeConn(rows))
    assert set(gaps) == {"knowledge_reviews"}
    assert gaps["knowledge_reviews"] == sorted(
        db_mod.BUSINESS_TABLE_COLUMNS["knowledge_reviews"]
    )
