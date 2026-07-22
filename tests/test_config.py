"""Sanity checks for YAML config loaders."""

from __future__ import annotations

from paca.core import config


def test_models_yaml_loads() -> None:
    cfg = config.load_models()
    assert "claude_fast" in cfg.profiles
    assert cfg.profiles["claude_fast"].provider == "claude"
    assert cfg.profiles["local"].provider == "omlx"
    assert cfg.profiles["local"].fallback_profile == "deepseek_smart"
    assert cfg.profiles["local_structured"].fallback_profile == "deepseek_structured"
    assert cfg.profiles["deepseek_smart"].provider == "deepseek"
    assert cfg.profiles["deepseek_structured"].provider == "deepseek"


def test_echo_agent_loads() -> None:
    cfg = config.load_agent("echo")
    assert cfg.name == "echo"
    assert cfg.tools == []
    assert "echo smoke-test" in cfg.resolved_instructions()


def test_list_agents_includes_echo() -> None:
    assert "echo" in config.list_agents()


def test_knowledge_artifact_editor_loads_as_db_free_agent() -> None:
    cfg = config.load_agent("knowledge_artifact_editor")
    assert cfg.name == "knowledge_artifact_editor"
    assert cfg.model_profile == "local"
    assert cfg.markdown is False
    assert cfg.tools == []
    assert cfg.extra["db"] is False
    assert cfg.extra["shared_context"] is False
    assert "clean the body" in cfg.resolved_instructions()


def test_knowledge_frontmatter_loads_as_db_free_agent() -> None:
    cfg = config.load_agent("knowledge_frontmatter")
    assert cfg.name == "knowledge_frontmatter"
    assert cfg.model_profile == "local"
    assert cfg.tools == []
    assert cfg.extra["db"] is False
    assert cfg.extra["shared_context"] is False
    assert "Return JSON only" in cfg.resolved_instructions()


def test_knowledge_frontmatter_has_locale_variants() -> None:
    cfg = config.load_agent("knowledge_frontmatter")
    zh = cfg.resolved_instructions("zh")
    en = cfg.resolved_instructions("en")
    assert zh != en
    assert "简体中文" in zh
    assert "in English" in en


def test_knowledge_tag_translator_loads_with_locale_variants() -> None:
    cfg = config.load_agent("knowledge_tag_translator")
    assert cfg.name == "knowledge_tag_translator"
    assert cfg.model_profile == "local_structured"
    assert cfg.extra["db"] is False
    assert cfg.resolved_instructions("zh") != cfg.resolved_instructions("en")


def test_workflow_yaml_loads_with_exposure() -> None:
    cfg = config.load_workflow("knowledge_ingest")
    assert cfg.name == "knowledge_ingest"
    assert cfg.factory == "paca.workflows.knowledge_ingest:build"
    assert cfg.expose.tool.enabled is True
    assert cfg.expose.tool.name == "knowledge_ingest_workflow"
