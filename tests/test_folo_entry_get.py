"""Tests for ``paca.integrations.info_radar.folo.entry_get``."""

from __future__ import annotations

import json
import subprocess

import pytest

from paca.integrations.info_radar import folo


def _result(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["folocli", "entry", "get"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_entry_get_happy_path(monkeypatch) -> None:
    envelope = {
        "ok": True,
        "data": {
            "entries": {
                "id": "abc",
                "title": "T",
                "content": "<p>body</p>",
            }
        },
        "error": None,
    }
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result(json.dumps(envelope)))

    entries = folo.entry_get("abc")

    assert entries["id"] == "abc"
    assert entries["content"] == "<p>body</p>"


def test_entry_get_ok_false_raises(monkeypatch) -> None:
    envelope = {
        "ok": False,
        "data": None,
        "error": {"code": "NOT_FOUND", "message": "no such entry"},
    }
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result(json.dumps(envelope)))

    with pytest.raises(RuntimeError, match="NOT_FOUND"):
        folo.entry_get("abc")


def test_entry_get_timeout_raises(monkeypatch) -> None:
    def boom(*a, **kw):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=kw.get("timeout", 0))

    monkeypatch.setattr(folo.subprocess, "run", boom)

    with pytest.raises(RuntimeError, match="timed out"):
        folo.entry_get("abc", timeout=1)


def test_entry_get_missing_entries_raises(monkeypatch) -> None:
    envelope = {"ok": True, "data": {}, "error": None}
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result(json.dumps(envelope)))

    with pytest.raises(RuntimeError, match="data.entries missing"):
        folo.entry_get("abc")


def test_entry_get_non_json_raises(monkeypatch) -> None:
    monkeypatch.setattr(folo.subprocess, "run", lambda *a, **kw: _result("not json", returncode=0))

    with pytest.raises(RuntimeError, match="non-JSON"):
        folo.entry_get("abc")


def test_entry_get_missing_envelope_key_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        folo.subprocess, "run", lambda *a, **kw: _result(json.dumps({"data": {}}))
    )

    with pytest.raises(RuntimeError, match="missing 'ok'"):
        folo.entry_get("abc")


def test_entry_get_rejects_empty_source_id() -> None:
    with pytest.raises(RuntimeError, match="non-empty source_id"):
        folo.entry_get("")
