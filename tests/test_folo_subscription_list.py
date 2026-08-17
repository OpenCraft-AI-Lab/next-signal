"""Tests for ``next_signal.integrations.info_radar.folo.subscription_list``.

``subscription_list`` shells out twice — ``subscription list`` for the inventory
and ``unread list`` for the counts — so the ``subprocess.run`` stand-in here
answers per folocli subcommand rather than replying the same thing to both.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from next_signal.core.secrets import delete_secret, save_secret
from next_signal.integrations.info_radar import folo

_NO_UNREAD = {"ok": True, "data": {"total": 0, "items": []}}


@pytest.fixture(autouse=True)
def _folo_token() -> None:
    """Every folocli call now requires the token before it spawns anything."""
    save_secret("FOLO_TOKEN", "test-token")


def test_missing_token_raises_before_spawning(monkeypatch) -> None:
    """The failure is ours, and it happens before folocli is ever invoked."""
    delete_secret("FOLO_TOKEN")
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        folo.subprocess, "run", lambda args, **kw: spawned.append(list(args))
    )

    with pytest.raises(RuntimeError, match="FOLO_TOKEN is not configured.*settings page"):
        folo.subscription_list()

    assert spawned == []


def _result(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["folocli", "subscription", "list"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _dispatch(subscriptions, unread=None, calls=None):
    """``subprocess.run`` stand-in answering per folocli subcommand.

    Each reply is an envelope dict, raw stdout, or a callable to invoke (so a
    test can make exactly one of the two calls blow up).
    """
    unread = _NO_UNREAD if unread is None else unread

    def run(args, **kwargs):
        if calls is not None:
            calls.append(list(args))
        reply = unread if list(args[-2:]) == ["unread", "list"] else subscriptions
        if callable(reply):
            return reply(args, **kwargs)
        return _result(reply if isinstance(reply, str) else json.dumps(reply))

    return run


def test_subscription_list_happy_path(monkeypatch) -> None:
    envelope = {
        "ok": True,
        "data": {
            "subscriptions": [
                {
                    "id": "feed_1",
                    "feedId": "feed_1",
                    "title": "Simon Willison's Weblog",
                    "feedUrl": "https://simonwillison.net/atom/everything/",
                    "siteUrl": "https://simonwillison.net/",
                    "category": {"title": "Blogs"},
                }
            ]
        },
    }
    unread = {"ok": True, "data": {"total": 12, "items": [{"feedId": "feed_1", "unreadCount": 12}]}}
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(envelope, unread))

    rows = folo.subscription_list()

    assert rows == [
        {
            "id": "feed_1",
            "title": "Simon Willison's Weblog",
            "feedUrl": "https://simonwillison.net/atom/everything/",
            "siteUrl": "https://simonwillison.net/",
            "category": "Blogs",
            "unread": 12,
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
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(envelope))

    rows = folo.subscription_list()

    assert rows == [
        {
            "id": "41380753238287360",
            "title": "硅谷101 - YouTube",
            "feedUrl": "rsshub://youtube/user/%40TheValley101",
            "siteUrl": "https://www.youtube.com/@TheValley101",
            "category": "Recommended",
            "unread": 0,
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
            }
        ],
    }
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(envelope))

    [row] = folo.subscription_list()

    assert row["title"] == "HN"
    assert row["feedUrl"] == "https://hnrss.org/frontpage"
    assert row["category"] == "Aggregators"


def test_subscription_list_merges_unread_by_feed_id(monkeypatch) -> None:
    envelope = {
        "ok": True,
        "data": {
            "subscriptions": [
                # A stale row-level count must lose to the unread list, which is
                # the only authority on unread now.
                {"feedId": "has_unread", "title": "Busy", "unreadCount": 99},
                {"feedId": "no_unread", "title": "Quiet"},
                {"title": "No feed id at all"},
            ]
        },
    }
    unread = {
        "ok": True,
        "data": {
            "total": 183,
            "items": [
                {"sourceType": "feed", "feedId": "has_unread", "unreadCount": 183},
                {"sourceType": "feed", "feedId": "not_subscribed", "unreadCount": 7},
            ],
        },
    }
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(envelope, unread))

    rows = folo.subscription_list()

    assert [row["unread"] for row in rows] == [183, 0, 0]


def test_subscription_list_matches_unread_on_nested_feed_id(monkeypatch) -> None:
    envelope = {
        "ok": True,
        "data": {"subscriptions": [{"feeds": {"id": "nested_1", "title": "Nested"}}]},
    }
    unread = {"ok": True, "data": {"items": [{"feedId": "nested_1", "unreadCount": 4}]}}
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(envelope, unread))

    [row] = folo.subscription_list()

    assert row["unread"] == 4


def test_subscription_list_drops_updated_at(monkeypatch) -> None:
    envelope = {
        "ok": True,
        "data": {
            "subscriptions": [
                {"feedId": "f1", "title": "T", "createdAt": "2026-05-25T02:51:17.591Z"}
            ]
        },
    }
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(envelope))

    [row] = folo.subscription_list()

    assert "updatedAt" not in row


def test_subscription_list_uses_argv_override(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("FOLO_CLI_ARGV", "folocli-dev --profile test")
    monkeypatch.setattr(folo.subprocess, "run", _dispatch({"ok": True, "data": []}, calls=calls))

    assert folo.subscription_list() == []
    assert [call[-2:] for call in calls] == [["subscription", "list"], ["unread", "list"]]
    for call in calls:
        assert call[:3] == ["folocli-dev", "--profile", "test"]


def test_subscription_list_ok_false_raises(monkeypatch) -> None:
    envelope = {
        "ok": False,
        "data": None,
        "error": {"code": "UNAUTHORIZED", "message": "login required"},
    }
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(envelope))

    with pytest.raises(RuntimeError, match="UNAUTHORIZED"):
        folo.subscription_list()


def test_subscription_list_non_json_raises(monkeypatch) -> None:
    monkeypatch.setattr(folo.subprocess, "run", _dispatch("not json"))

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
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(envelope))

    with pytest.raises(RuntimeError, match="not a list"):
        folo.subscription_list()


def _ok_subscriptions() -> dict:
    return {"ok": True, "data": {"subscriptions": [{"feedId": "f1", "title": "T"}]}}


def test_subscription_list_raises_when_unread_ok_false(monkeypatch) -> None:
    unread = {
        "ok": False,
        "data": None,
        "error": {"code": "UNAUTHORIZED", "message": "login required"},
    }
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(_ok_subscriptions(), unread))

    with pytest.raises(RuntimeError, match="unread list ok=false"):
        folo.subscription_list()


def test_subscription_list_raises_when_unread_non_json(monkeypatch) -> None:
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(_ok_subscriptions(), "not json"))

    with pytest.raises(RuntimeError, match="unread list non-JSON"):
        folo.subscription_list()


def test_subscription_list_raises_when_unread_times_out(monkeypatch) -> None:
    def boom(args, **kw):
        raise subprocess.TimeoutExpired(cmd=args, timeout=kw.get("timeout", 0))

    monkeypatch.setattr(folo.subprocess, "run", _dispatch(_ok_subscriptions(), boom))

    with pytest.raises(RuntimeError, match="unread list timed out"):
        folo.subscription_list()


def test_subscription_list_raises_when_unread_shape_is_bad(monkeypatch) -> None:
    unread = {"ok": True, "data": {"items": {}}}
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(_ok_subscriptions(), unread))

    with pytest.raises(RuntimeError, match="unread list: .*not a list"):
        folo.subscription_list()


def test_subscription_list_raises_when_unread_has_no_rows_key(monkeypatch) -> None:
    # folocli renaming data.items would otherwise render a real-looking 0 on
    # every feed — the exact failure the unread merge exists to remove.
    unread = {"ok": True, "data": {"total": 710, "unreadItems": [{"feedId": "f1"}]}}
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(_ok_subscriptions(), unread))

    with pytest.raises(RuntimeError, match="unread list: no rows key"):
        folo.subscription_list()


def test_subscription_list_raises_when_data_has_no_rows_key(monkeypatch) -> None:
    envelope = {"ok": True, "data": {"total": 3, "records": []}}
    monkeypatch.setattr(folo.subprocess, "run", _dispatch(envelope))

    with pytest.raises(RuntimeError, match="subscription list: no rows key"):
        folo.subscription_list()
