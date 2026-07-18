"""CLI surface tests for ``paca info-radar analyze``."""

from __future__ import annotations

from typer.testing import CliRunner

from paca.interfaces import cli


def test_analyze_prints_counters(monkeypatch) -> None:
    captured = {}

    def fake_run(*, limit=None, source=None):
        captured["limit"] = limit
        captured["source"] = source
        return {
            "items_total": 5,
            "tier1_kept": 3,
            "tier1_dropped": 2,
            "tier1_error": 0,
            "tier2_ok": 3,
            "tier2_fallback": 0,
            "tier2_error": 0,
            "dedup_novel": 2,
            "dedup_duplicate": 1,
        }

    import paca.workflows.info_radar_analysis as pkg

    monkeypatch.setattr(pkg, "run", fake_run)

    result = CliRunner().invoke(cli.app, ["info-radar", "analyze", "--limit", "5"])

    assert result.exit_code == 0, result.output
    assert "items_total=5" in result.output
    assert "tier1_kept=3" in result.output
    assert "dedup_novel=2" in result.output
    assert captured["limit"] == 5
    assert captured["source"] is None


def test_analyze_forwards_source_filter(monkeypatch) -> None:
    captured = {}

    def fake_run(*, limit=None, source=None):
        captured["limit"] = limit
        captured["source"] = source
        return {"items_total": 0}

    import paca.workflows.info_radar_analysis as pkg

    monkeypatch.setattr(pkg, "run", fake_run)

    result = CliRunner().invoke(cli.app, ["info-radar", "analyze", "--source", "folo_x"])

    assert result.exit_code == 0
    assert captured["source"] == "folo_x"
    assert "items_total=0" in result.output


def test_subscriptions_prints_json(monkeypatch) -> None:
    from paca.integrations.info_radar import folo

    monkeypatch.setattr(
        folo,
        "subscription_list",
        lambda: [
            {
                "id": "feed_1",
                "title": "Feed",
                "feedUrl": "https://example.com/feed",
                "siteUrl": None,
                "category": "Blogs",
                "unread": 2,
                "updatedAt": None,
            }
        ],
    )

    result = CliRunner().invoke(cli.app, ["info-radar", "subscriptions", "--json"])

    assert result.exit_code == 0, result.output
    assert '"title": "Feed"' in result.output
    assert '"unread": 2' in result.output
