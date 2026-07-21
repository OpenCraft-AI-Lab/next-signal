"""Locale-aware instructions resolution (core-agents: locale variants)."""

from __future__ import annotations

from pathlib import Path

import pytest

from paca.core import config
from paca.core.config import AgentConfig


def _cfg() -> AgentConfig:
    return AgentConfig(
        name="probe",
        model_profile="local",
        instructions_file="agents/probe.md",
    )


@pytest.fixture
def prompts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "probe.md").write_text("base zh prompt", encoding="utf-8")
    monkeypatch.setattr(config, "PROMPTS_DIR", tmp_path)
    return agents


def test_default_locale_reads_base(prompts_dir: Path) -> None:
    assert _cfg().resolved_instructions() == "base zh prompt"
    assert _cfg().resolved_instructions("zh") == "base zh prompt"


def test_non_default_locale_reads_variant(prompts_dir: Path) -> None:
    (prompts_dir / "probe.en.md").write_text("english prompt", encoding="utf-8")
    assert _cfg().resolved_instructions("en") == "english prompt"


def test_missing_variant_falls_back_to_base(
    prompts_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        text = _cfg().resolved_instructions("en")
    assert text == "base zh prompt"
    assert any("instructions_locale_fallback" in r.message for r in caplog.records)
