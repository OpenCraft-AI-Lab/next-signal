"""Runner tests: per-source failure isolation, no DB required (store mocked)."""

from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from paca.collectors.info_radar import runner
from paca.collectors.info_radar.loader import SourceSpec


def _spec(name: str, *, argv: list[str] | None = None) -> SourceSpec:
    return SourceSpec(
        name=name,
        enabled=True,
        argv=argv or ["echo", name],
        timeout_sec=5,
        parser_name="folo_timeline",
    )


@pytest.fixture
def fake_run(monkeypatch):
    """Stub subprocess.run with per-argv canned responses."""

    plan: dict[str, dict[str, Any]] = {}

    def configure(name: str, *, stdout: str = "", stderr: str = "", returncode: int = 0,
                  raise_exc: type[BaseException] | None = None) -> None:
        plan[name] = {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": returncode,
            "raise_exc": raise_exc,
        }

    def fake(argv, **kwargs):
        name = argv[-1]
        if name not in plan:
            raise AssertionError(f"unexpected subprocess.run call: {argv}")
        recipe = plan[name]
        if recipe["raise_exc"] is not None:
            if recipe["raise_exc"] is subprocess.TimeoutExpired:
                raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 0))
            raise recipe["raise_exc"]
        return subprocess.CompletedProcess(
            args=argv,
            returncode=recipe["returncode"],
            stdout=recipe["stdout"],
            stderr=recipe["stderr"],
        )

    monkeypatch.setattr(runner.subprocess, "run", fake)
    return configure


@pytest.fixture
def fake_store(monkeypatch):
    """Capture upsert_items calls; sweep_expired is a no-op."""
    upserts: list[tuple[str, int]] = []

    def fake_upsert(source, items):
        items_list = list(items)
        upserts.append((source, len(items_list)))
        return (len(items_list), 0)

    monkeypatch.setattr(runner.store, "upsert_items", fake_upsert)
    monkeypatch.setattr(runner.store, "sweep_expired", lambda: 0)
    return upserts


def _folo_envelope(ids: list[str]) -> str:
    entries = []
    for i in ids:
        entries.append({
            "entries": {
                "id": i,
                "title": f"title-{i}",
                "url": f"https://example.com/{i}",
                "description": "x",
                "publishedAt": "2026-05-25T00:00:00Z",
            },
        })
    return json.dumps({"ok": True, "data": {"entries": entries}, "error": None})


def test_one_source_succeeds(monkeypatch, fake_run, fake_store):
    monkeypatch.setattr(runner, "load_sources", lambda: [_spec("good")])
    fake_run("good", stdout=_folo_envelope(["a", "b", "c"]))

    [result] = runner.run_all()

    assert result.name == "good"
    assert result.error is None
    assert result.written == 3
    assert fake_store == [("good", 3)]


def test_failure_isolation_one_fails_other_succeeds(monkeypatch, fake_run, fake_store):
    """Per-source failure isolation per design D9."""
    monkeypatch.setattr(runner, "load_sources", lambda: [_spec("bad"), _spec("good")])
    fake_run("bad", returncode=2, stderr="boom")
    fake_run("good", stdout=_folo_envelope(["x"]))

    results = runner.run_all()

    assert len(results) == 2
    bad, good = results
    assert bad.name == "bad" and bad.error and "exit 2" in bad.error
    assert good.name == "good" and good.error is None and good.written == 1
    assert fake_store == [("good", 1)]
    assert runner.all_failed(results) is False


def test_all_sources_fail_marks_all_failed(monkeypatch, fake_run, fake_store):
    monkeypatch.setattr(runner, "load_sources", lambda: [_spec("a"), _spec("b")])
    fake_run("a", returncode=1, stderr="bad1")
    fake_run("b", returncode=1, stderr="bad2")

    results = runner.run_all()

    assert runner.all_failed(results) is True
    assert fake_store == []


def test_timeout_isolated(monkeypatch, fake_run, fake_store):
    monkeypatch.setattr(runner, "load_sources", lambda: [_spec("slow"), _spec("fast")])
    fake_run("slow", raise_exc=subprocess.TimeoutExpired)
    fake_run("fast", stdout=_folo_envelope(["x"]))

    slow, fast = runner.run_all()

    assert "timed out" in (slow.error or "")
    assert fast.error is None and fast.written == 1


def test_parser_error_isolated(monkeypatch, fake_run, fake_store):
    monkeypatch.setattr(runner, "load_sources", lambda: [_spec("bad-shape")])
    fake_run("bad-shape", stdout='{"ok": false, "error": {"code": "X", "message": "y"}}')

    [result] = runner.run_all()

    assert result.error and "parser" in result.error and "ok=false" in result.error


def test_only_filter_runs_just_named_source(monkeypatch, fake_run, fake_store):
    monkeypatch.setattr(runner, "load_sources", lambda: [_spec("a"), _spec("b")])
    fake_run("b", stdout=_folo_envelope(["1"]))

    results = runner.run_all(only="b")

    assert [r.name for r in results] == ["b"]


def test_disabled_source_skipped(monkeypatch, fake_run, fake_store):
    disabled = SourceSpec(name="off", enabled=False, argv=["echo", "off"],
                          timeout_sec=5, parser_name="folo_timeline")
    monkeypatch.setattr(runner, "load_sources", lambda: [disabled])

    assert runner.run_all() == []


# ---- scheduler-facing thin shell (paca.workflows.info_radar_pull) -----------


def test_pull_shell_summarizes_results(monkeypatch):
    from paca.workflows import info_radar_pull

    results = [
        runner.SourceResult(name="a", written=2, skipped=1, error=None),
        runner.SourceResult(name="b", written=0, skipped=0, error="boom"),
    ]
    monkeypatch.setattr(runner, "run_all", lambda: results)

    assert info_radar_pull.run() == {
        "sources_run": 2,
        "items_written": 2,
        "items_skipped": 1,
        "errors": [{"source": "b", "error": "boom"}],
        "all_failed": False,
    }


def test_pull_shell_factory_fails_loud():
    from paca.workflows import info_radar_pull

    with pytest.raises(NotImplementedError, match="not an AgentOS workflow"):
        info_radar_pull.factory()
