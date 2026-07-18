"""Loader tests for info-radar source descriptors."""

from __future__ import annotations

from pathlib import Path

import pytest

from paca.collectors.info_radar.loader import load_sources


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_load_sources_accepts_valid_entry(tmp_path: Path) -> None:
    cfg = tmp_path / "sources.yaml"
    _write(
        cfg,
        """
sources:
  - name: folo_test
    enabled: true
    cli:
      argv: ["echo", "hi"]
      timeout_sec: 10
    parser: folo_timeline
""",
    )

    [spec] = load_sources(cfg)

    assert spec.name == "folo_test"
    assert spec.enabled is True
    assert spec.argv == ["echo", "hi"]
    assert spec.timeout_sec == 10
    assert spec.parser_name == "folo_timeline"
    assert callable(spec.parser)


def test_load_sources_rejects_unknown_parser(tmp_path: Path) -> None:
    cfg = tmp_path / "sources.yaml"
    _write(
        cfg,
        """
sources:
  - name: x
    cli:
      argv: ["echo"]
    parser: typo_parser
""",
    )

    with pytest.raises(RuntimeError, match="parser 'typo_parser' is not registered"):
        load_sources(cfg)


def test_load_sources_rejects_argv_template_in_v1(tmp_path: Path) -> None:
    cfg = tmp_path / "sources.yaml"
    _write(
        cfg,
        """
sources:
  - name: x
    cli:
      argv_template: ["${OPENCLI_BIN_ARGV}", "zhihu"]
    parser: folo_timeline
""",
    )

    with pytest.raises(RuntimeError, match="argv_template.*not supported in v1"):
        load_sources(cfg)


def test_load_sources_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    cfg = tmp_path / "sources.yaml"
    _write(
        cfg,
        """
sources:
  - name: x
    cli:
      argv: ["echo"]
    parser: folo_timeline
    extras: oops
""",
    )

    with pytest.raises(RuntimeError, match="unknown keys"):
        load_sources(cfg)


def test_load_sources_rejects_unknown_cli_keys(tmp_path: Path) -> None:
    cfg = tmp_path / "sources.yaml"
    _write(
        cfg,
        """
sources:
  - name: x
    cli:
      argv: ["echo"]
      retry: 3
    parser: folo_timeline
""",
    )

    with pytest.raises(RuntimeError, match="unknown cli keys"):
        load_sources(cfg)


def test_load_sources_rejects_duplicate_names(tmp_path: Path) -> None:
    cfg = tmp_path / "sources.yaml"
    _write(
        cfg,
        """
sources:
  - name: dup
    cli: { argv: ["echo"] }
    parser: folo_timeline
  - name: dup
    cli: { argv: ["echo"] }
    parser: folo_timeline
""",
    )

    with pytest.raises(RuntimeError, match="duplicate source name 'dup'"):
        load_sources(cfg)


def test_load_sources_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not found"):
        load_sources(tmp_path / "absent.yaml")
