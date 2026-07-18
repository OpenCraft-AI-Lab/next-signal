"""Tests for ``paca.integrations.info_radar.folo.subscription_list``."""

from __future__ import annotations

import json
import subprocess

import pytest

from paca.integrations.info_radar import folo


def _result(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["folocli", "subscription", "list"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_subscription_list_happy_path(monkeypatch) -> None:
    envelope = {
        "ok": True,
        "data": {
            "subscriptions": [
                {
                    "id": "feed_1",
                    "title": "Simon Willison's Weblog",
                    "feedUrl": "https://simonwillison.net/atom/everything/",
                    "siteUrl": "https://simonwillison.net/",
                    "category": {"title": "Blogs"},
                    "unreadCount": 12,
                    "updatedAt": "2026-05-30T12:00:00Z",
                }
            ]
        },
    }
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result(json.dumps(envelope)))

    rows = folo.subscription_list()

    assert rows == [
        {
            "id": "feed_1",
            "title": "Simon Willison's Weblog",
            "feedUrl": "https://simonwillison.net/atom/everything/",
            "siteUrl": "https://simonwillison.net/",
            "category": "Blogs",
            "unread": 12,
            "updatedAt": "2026-05-30T12:00:00Z",
        }
    ]


def test_subscription_list_accepts_nested_feed_shape(monkeypatch) -> None:
    envelope = {
        "ok": True,
        "data": {
            "subscriptions": [
                {
                    "feedId": "41380753238287360",
                    "view": 3,
                    "category": "Recommended",
                    "title": None,
                    "createdAt": "2026-05-25T02:51:17.591Z",
                    "feeds": {
                        "id": "41380753238287360",
                        "url": "rsshub://youtube/user/%40TheValley101",
                        "title": "硅谷101 - YouTube",
                        "siteUrl": "https://www.youtube.com/@TheValley101",
                    },
                }
            ]
        },
    }
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result(json.dumps(envelope)))

    rows = folo.subscription_list()

    assert rows == [
        {
            "id": "41380753238287360",
            "title": "硅谷101 - YouTube",
            "feedUrl": "rsshub://youtube/user/%40TheValley101",
            "siteUrl": "https://www.youtube.com/@TheValley101",
            "category": "Recommended",
            "unread": None,
            "updatedAt": "2026-05-25T02:51:17.591Z",
        }
    ]


def test_subscription_list_accepts_data_list(monkeypatch) -> None:
    envelope = {
        "ok": True,
        "data": [
            {
                "name": "HN",
                "url": "https://hnrss.org/frontpage",
                "view": "Aggregators",
                "unread": "5",
            }
        ],
    }
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result(json.dumps(envelope)))

    [row] = folo.subscription_list()

    assert row["title"] == "HN"
    assert row["feedUrl"] == "https://hnrss.org/frontpage"
    assert row["category"] == "Aggregators"
    assert row["unread"] == 5


def test_subscription_list_uses_argv_override(monkeypatch) -> None:
    captured = {}
    envelope = {"ok": True, "data": []}

    def fake_run(args, **kw):
        captured["args"] = args
        return _result(json.dumps(envelope))

    monkeypatch.setenv("FOLO_CLI_ARGV", "folocli-dev --profile test")
    monkeypatch.setattr(folo.subprocess, "run", fake_run)

    assert folo.subscription_list() == []
    assert captured["args"][:2] == ["folocli-dev", "--profile"]
    assert captured["args"][-2:] == ["subscription", "list"]


def test_subscription_list_ok_false_raises(monkeypatch) -> None:
    envelope = {
        "ok": False,
        "data": None,
        "error": {"code": "UNAUTHORIZED", "message": "login required"},
    }
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result(json.dumps(envelope)))

    with pytest.raises(RuntimeError, match="UNAUTHORIZED"):
        folo.subscription_list()


def test_subscription_list_non_json_raises(monkeypatch) -> None:
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result("not json"))

    with pytest.raises(RuntimeError, match="non-JSON"):
        folo.subscription_list()


def test_subscription_list_timeout_raises(monkeypatch) -> None:
    def boom(*a, **kw):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=kw.get("timeout", 0))

    monkeypatch.setattr(folo.subprocess, "run", boom)

    with pytest.raises(RuntimeError, match="timed out"):
        folo.subscription_list(timeout=1)


def test_subscription_list_rejects_bad_shape(monkeypatch) -> None:
    envelope = {"ok": True, "data": {"subscriptions": {}}}
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result(json.dumps(envelope)))

    with pytest.raises(RuntimeError, match="not a list"):
        folo.subscription_list()
