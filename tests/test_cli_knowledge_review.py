"""CLI surface tests for ``paca knowledge review``."""

from __future__ import annotations

from typer.testing import CliRunner

from paca.interfaces import cli

import paca.workflows.knowledge_review as pkg


def test_review_prints_counts(monkeypatch) -> None:
    monkeypatch.setattr(
        pkg, "run", lambda: {"enrolled": 3, "unenrolled": 1, "due": 9}
    )

    result = CliRunner().invoke(cli.app, ["knowledge", "review"])

    assert result.exit_code == 0, result.output
    assert "enrolled=3" in result.output
    assert "unenrolled=1" in result.output
    assert "due=9" in result.output


def test_empty_wiki_exits_non_zero(monkeypatch) -> None:
    def boom():
        raise RuntimeError("wiki has no markdown docs: /wiki; refusing to reconcile")

    monkeypatch.setattr(pkg, "run", boom)

    result = CliRunner().invoke(cli.app, ["knowledge", "review"])

    assert result.exit_code == 1
    assert "refusing to reconcile" in result.output
