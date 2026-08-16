"""Credential store: read, write, and the per-spawn child environment."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from next_signal.core.secrets import (
    CREDENTIAL_NAMES,
    child_env,
    delete_secret,
    get_secret,
    load_secrets,
    require_secret,
    save_secret,
)


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "secrets.json"


def test_absent_file_is_an_empty_store(store: Path) -> None:
    assert load_secrets(store) == {}
    assert get_secret("OPENAI_API_KEY", store) == ""


def test_absent_credential_raises_pointing_at_settings(store: Path) -> None:
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY.*Settings"):
        require_secret("OPENAI_API_KEY", store)


@pytest.mark.parametrize(
    "body",
    ["{ not json", '["a", "b"]', '{"OPENAI_API_KEY": 42}'],
    ids=["unparseable", "not-an-object", "non-string-value"],
)
def test_malformed_store_fails_loud(store: Path, body: str) -> None:
    store.write_text(body, encoding="utf-8")
    with pytest.raises(RuntimeError, match="credential store"):
        load_secrets(store)


def test_save_and_read_round_trip(store: Path) -> None:
    save_secret("DEEPSEEK_API_KEY", "sk-example", store)

    assert get_secret("DEEPSEEK_API_KEY", store) == "sk-example"
    assert require_secret("DEEPSEEK_API_KEY", store) == "sk-example"
    assert json.loads(store.read_text(encoding="utf-8")) == {
        "DEEPSEEK_API_KEY": "sk-example"
    }


def test_save_replaces_without_disturbing_others(store: Path) -> None:
    save_secret("DEEPSEEK_API_KEY", "first", store)
    save_secret("GITHUB_TOKEN", "gh-token", store)
    save_secret("DEEPSEEK_API_KEY", "second", store)

    assert load_secrets(store) == {
        "DEEPSEEK_API_KEY": "second",
        "GITHUB_TOKEN": "gh-token",
    }


def test_delete_removes_one_and_is_idempotent(store: Path) -> None:
    save_secret("GITHUB_TOKEN", "gh-token", store)
    save_secret("FOLO_TOKEN", "folo-token", store)

    delete_secret("GITHUB_TOKEN", store)
    delete_secret("GITHUB_TOKEN", store)

    assert load_secrets(store) == {"FOLO_TOKEN": "folo-token"}


def test_empty_value_is_refused(store: Path) -> None:
    with pytest.raises(RuntimeError, match="empty value"):
        save_secret("GITHUB_TOKEN", "   ", store)


def test_write_leaves_no_temp_file_behind(store: Path) -> None:
    save_secret("OPENAI_API_KEY", "sk-example", store)

    assert [p.name for p in store.parent.iterdir()] == ["secrets.json"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes only")
def test_store_is_owner_only(store: Path) -> None:
    save_secret("OPENAI_API_KEY", "sk-example", store)

    assert store.stat().st_mode & 0o777 == 0o600


def test_malformed_name_is_refused(store: Path) -> None:
    with pytest.raises(RuntimeError, match="credential name"):
        save_secret("lowercase_key", "value", store)


def test_known_credential_names_are_the_documented_set() -> None:
    assert set(CREDENTIAL_NAMES) == {
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_GENERATIVE_AI_API_KEY",
        "DEEPSEEK_API_KEY",
        "OMLX_API_KEY",
        "EMBEDDING_API_KEY",
        "VOYAGE_API_KEY",
        "GITHUB_TOKEN",
        "FOLO_TOKEN",
    }


def test_operator_defined_name_is_storable(store: Path) -> None:
    """The compatible embedding endpoint names its own credential."""
    save_secret("MY_EMBEDDING_API_KEY", "sk-custom", store)

    assert get_secret("MY_EMBEDDING_API_KEY", store) == "sk-custom"


def test_child_env_carries_only_named_credentials(store: Path) -> None:
    save_secret("FOLO_TOKEN", "folo-token", store)
    save_secret("GITHUB_TOKEN", "gh-token", store)

    env = child_env(["FOLO_TOKEN"], store)

    assert env["FOLO_TOKEN"] == "folo-token"
    assert "GITHUB_TOKEN" not in env


def test_child_env_omits_an_absent_credential(store: Path) -> None:
    env = child_env(["FOLO_TOKEN"], store)

    assert "FOLO_TOKEN" not in env


def test_child_env_drops_an_inherited_value_absent_from_the_store(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leftover environment value must not authenticate a child."""
    monkeypatch.setenv("FOLO_TOKEN", "stale-from-environment")

    env = child_env(["FOLO_TOKEN"], store)

    assert "FOLO_TOKEN" not in env


def test_child_env_does_not_mutate_the_parent_environment(store: Path) -> None:
    save_secret("FOLO_TOKEN", "folo-token", store)
    before = os.environ.copy()

    child_env(["FOLO_TOKEN"], store)

    assert os.environ == before


def test_child_env_strips_an_unrequested_credential_from_the_environment(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leftover `.env` value must not reach a child that never asked for it."""
    monkeypatch.setenv("GITHUB_TOKEN", "stale-from-dotenv")

    env = child_env(["FOLO_TOKEN"], store)

    assert "GITHUB_TOKEN" not in env


def test_child_env_preserves_the_inherited_environment(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOLO_CLI_ARGV", "folo")

    env = child_env(["FOLO_TOKEN"], store)

    assert env["FOLO_CLI_ARGV"] == "folo"
