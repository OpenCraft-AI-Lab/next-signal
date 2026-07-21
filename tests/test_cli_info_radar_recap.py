"""CLI surface tests for ``paca info-radar recap``."""

from __future__ import annotations

from typer.testing import CliRunner

from paca.interfaces import cli

import paca.workflows.info_radar_recap as pkg


_DONE = {
    "status": "done",
    "since": "2026-07-13",
    "until": "2026-07-19",
    "min_score": 0,
    "novel_only": False,
    "headline": "Inference prices moved",
    "themes": [
        {"title": "Price war", "narrative": "n", "item_ids": [12, 31, 48]},
        {"title": "Local stacks", "narrative": "n", "item_ids": [7]},
    ],
    "item_count": 60,
    "considered_count": 143,
}


def test_recap_prints_headline_themes_and_coverage(monkeypatch) -> None:
    monkeypatch.setattr(pkg, "run", lambda **kw: _DONE)

    result = CliRunner().invoke(
        cli.app,
        ["info-radar", "recap", "--since", "2026-07-13", "--until", "2026-07-19"],
    )

    assert result.exit_code == 0, result.output
    assert "Inference prices moved" in result.output
    assert "Price war [3 cited]" in result.output
    assert "top 60 of 143" in result.output


def test_recap_forwards_gate_and_regenerate_flags(monkeypatch) -> None:
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _DONE

    monkeypatch.setattr(pkg, "run", fake_run)

    result = CliRunner().invoke(
        cli.app,
        [
            "info-radar",
            "recap",
            "--since",
            "2026-07-13",
            "--until",
            "2026-07-19",
            "--min-score",
            "70",
            "--novel-only",
            "--regenerate",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["min_score"] == 70
    assert captured["novel_only"] is True
    assert captured["regenerate"] is True


def test_cached_recap_is_labelled(monkeypatch) -> None:
    monkeypatch.setattr(pkg, "run", lambda **kw: {**_DONE, "status": "cached"})

    result = CliRunner().invoke(
        cli.app,
        ["info-radar", "recap", "--since", "2026-07-13", "--until", "2026-07-19"],
    )

    assert result.exit_code == 0, result.output
    assert "(cached)" in result.output


def test_empty_range_exits_zero_with_a_message(monkeypatch) -> None:
    monkeypatch.setattr(
        pkg,
        "run",
        lambda **kw: {
            "status": "empty",
            "since": "2026-07-13",
            "until": "2026-07-19",
            "min_score": 0,
            "novel_only": False,
            "considered_count": 0,
        },
    )

    result = CliRunner().invoke(
        cli.app,
        ["info-radar", "recap", "--since", "2026-07-13", "--until", "2026-07-19"],
    )

    assert result.exit_code == 0, result.output
    assert "no items cleared the gate" in result.output


def test_inverted_range_exits_non_zero(monkeypatch) -> None:
    def boom(**kwargs):
        raise RuntimeError("invalid recap range: until (2026-07-13) precedes since (2026-07-19)")

    monkeypatch.setattr(pkg, "run", boom)

    result = CliRunner().invoke(
        cli.app,
        ["info-radar", "recap", "--since", "2026-07-19", "--until", "2026-07-13"],
    )

    assert result.exit_code == 1
    assert "invalid recap range" in result.output


def test_generation_failure_exits_non_zero(monkeypatch) -> None:
    monkeypatch.setattr(
        pkg,
        "run",
        lambda **kw: {
            "status": "error",
            "error": "omlx unreachable",
            "since": "2026-07-13",
            "until": "2026-07-19",
            "min_score": 0,
            "novel_only": False,
        },
    )

    result = CliRunner().invoke(
        cli.app,
        ["info-radar", "recap", "--since", "2026-07-13", "--until", "2026-07-19"],
    )

    assert result.exit_code == 1
    assert "FAILED" in result.output
