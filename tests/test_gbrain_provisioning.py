"""GBrain initialisation state and provider-scoped credential injection."""

from __future__ import annotations

import json
from pathlib import Path

from next_signal.core import secrets
from next_signal.integrations import gbrain


def _write_brain(home: Path, **config: object) -> None:
    (home / ".gbrain").mkdir(parents=True, exist_ok=True)
    (home / ".gbrain" / "config.json").write_text(json.dumps(config), encoding="utf-8")


def test_brain_initialised_reports_three_states(tmp_path: Path) -> None:
    absent = tmp_path / "absent"
    absent.mkdir()
    assert gbrain.brain_initialised(gbrain_home=str(absent)) is False

    ready = tmp_path / "ready"
    _write_brain(ready, engine="postgres", embedding_model="openai:text-embedding-3-large")
    assert gbrain.brain_initialised(gbrain_home=str(ready)) is True

    broken = tmp_path / "broken"
    (broken / ".gbrain").mkdir(parents=True)
    (broken / ".gbrain" / "config.json").write_text("{not json", encoding="utf-8")
    assert gbrain.brain_initialised(gbrain_home=str(broken)) is None


def test_configured_embedding_model_reads_the_brain(tmp_path: Path) -> None:
    home = tmp_path / "brain"
    _write_brain(home, embedding_model="voyage:voyage-3")
    assert gbrain.configured_embedding_model(gbrain_home=str(home)) == "voyage:voyage-3"

    deferred = tmp_path / "deferred"
    _write_brain(deferred, engine="postgres")
    assert gbrain.configured_embedding_model(gbrain_home=str(deferred)) is None


def test_credential_follows_the_selected_provider() -> None:
    assert gbrain.credential_for_model("openai:text-embedding-3-large") == "OPENAI_API_KEY"
    assert gbrain.credential_for_model("voyage:voyage-3") == "VOYAGE_API_KEY"
    assert (
        gbrain.credential_for_model("google:text-embedding-004") == "GOOGLE_GENERATIVE_AI_API_KEY"
    )
    # Local runners take an endpoint, not a key.
    assert gbrain.credential_for_model("ollama:nomic-embed-text") is None
    assert gbrain.credential_for_model("lmstudio:whatever") is None
    # An unknown provider degrades to injecting nothing rather than raising,
    # because this sits on the read path for every gbrain call.
    assert gbrain.credential_for_model("nonesuch:model") is None


def test_local_provider_needs_no_credential(tmp_path: Path, monkeypatch) -> None:
    """A local brain resolves against an empty credential store."""
    home = tmp_path / "brain"
    _write_brain(home, embedding_model="ollama:nomic-embed-text")
    monkeypatch.setenv("GBRAIN_HOME", str(home))

    env = gbrain.gbrain_env()
    assert "OPENAI_API_KEY" not in env
    assert "VOYAGE_API_KEY" not in env


def test_only_the_selected_provider_credential_is_injected(tmp_path: Path, monkeypatch) -> None:
    secrets.save_secret("OPENAI_API_KEY", "sk-openai")
    secrets.save_secret("VOYAGE_API_KEY", "sk-voyage")

    home = tmp_path / "brain"
    _write_brain(home, embedding_model="voyage:voyage-3")
    monkeypatch.setenv("GBRAIN_HOME", str(home))

    env = gbrain.gbrain_env()
    assert env["VOYAGE_API_KEY"] == "sk-voyage"
    assert "OPENAI_API_KEY" not in env


def test_gbrain_init_refuses_an_initialised_brain(tmp_path: Path, monkeypatch) -> None:
    """The model sizes the schema, so a second init can only be a no-op or data loss."""
    from typer.testing import CliRunner

    from next_signal.interfaces.cli import app

    home = tmp_path / "brain"
    _write_brain(home, embedding_model="openai:text-embedding-3-large")
    monkeypatch.setenv("GBRAIN_HOME", str(home))

    result = CliRunner().invoke(
        app, ["knowledge", "gbrain-init", "--embedding-model", "voyage:voyage-3"]
    )

    assert result.exit_code != 0
    assert "already initialised" in str(result.exception)
    assert "openai:text-embedding-3-large" in str(result.exception)


def test_gbrain_init_refuses_an_unknown_provider(tmp_path: Path, monkeypatch) -> None:
    from typer.testing import CliRunner

    from next_signal.interfaces.cli import app

    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("GBRAIN_HOME", str(empty))

    result = CliRunner().invoke(
        app, ["knowledge", "gbrain-init", "--embedding-model", "nonesuch:model"]
    )

    assert result.exit_code != 0
    assert "unknown embedding provider" in str(result.exception)


def test_gbrain_init_refuses_a_missing_provider_credential(tmp_path: Path, monkeypatch) -> None:
    """Better than a permanent schema sitting behind a key nobody saved."""
    from typer.testing import CliRunner

    from next_signal.interfaces.cli import app

    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("GBRAIN_HOME", str(empty))

    result = CliRunner().invoke(
        app, ["knowledge", "gbrain-init", "--embedding-model", "openai:text-embedding-3-large"]
    )

    assert result.exit_code != 0
    assert "OPENAI_API_KEY" in str(result.exception)


def test_explicit_model_overrides_the_brain(tmp_path: Path, monkeypatch) -> None:
    """`gbrain-init` runs before a brain exists, so it names its own provider."""
    secrets.save_secret("OPENAI_API_KEY", "sk-openai")
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("GBRAIN_HOME", str(empty))

    env = gbrain.gbrain_env(embedding_model="openai:text-embedding-3-large")
    assert env["OPENAI_API_KEY"] == "sk-openai"

    local = gbrain.gbrain_env(embedding_model="ollama:nomic-embed-text")
    assert "OPENAI_API_KEY" not in local
