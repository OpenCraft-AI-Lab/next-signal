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
    monkeypatch.setattr(config, "PROMPTS_DIR", tmp_path)
    return agents


def test_locale_variant_is_preferred(prompts_dir: Path) -> None:
    # Multi-language agent: one file per locale, no unsuffixed base.
    (prompts_dir / "probe.zh.md").write_text("中文 prompt", encoding="utf-8")
    (prompts_dir / "probe.en.md").write_text("english prompt", encoding="utf-8")
    assert _cfg().resolved_instructions("en") == "english prompt"
    assert _cfg().resolved_instructions("zh") == "中文 prompt"


def test_unsuffixed_base_is_fallback(prompts_dir: Path) -> None:
    # Single-language agent: only the unsuffixed base exists; any locale uses it.
    (prompts_dir / "probe.md").write_text("single-language prompt", encoding="utf-8")
    assert _cfg().resolved_instructions("en") == "single-language prompt"
    assert _cfg().resolved_instructions("zh") == "single-language prompt"


def test_missing_variant_and_base_raises(prompts_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _cfg().resolved_instructions("en")
