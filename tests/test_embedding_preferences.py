from __future__ import annotations

import json

import pytest

from next_signal.core.embedding_preferences import (
    EmbeddingPreferences,
    configured_embedding_defaults,
    embedder_identity,
    load_embedding_preferences,
)

COMPATIBLE = {
    "base_url": "https://host.example/v1",
    "model": "bge-m3",
    "api_key_env": "MY_EMBED_KEY",
    "space_id": "house-bge-m3",
}


@pytest.fixture
def defaults() -> EmbeddingPreferences:
    return configured_embedding_defaults()


def test_configured_defaults_follow_models_yaml(defaults: EmbeddingPreferences) -> None:
    assert defaults.provider == "omlx"
    assert defaults.omlx.model == "Qwen3-Embedding-0.6B-8bit"
    assert defaults.openai.model == "text-embedding-3-small"
    # No fabricated generic endpoint: the repo has no honest default for one.
    assert defaults.openai_compatible is None


def test_absent_state_selects_the_local_baseline(tmp_path, defaults) -> None:
    assert load_embedding_preferences(tmp_path / "missing.json", defaults=defaults) == defaults


@pytest.mark.parametrize("provider", ["omlx", "openai"])
def test_partial_section_inherits_its_baseline(tmp_path, defaults, provider: str) -> None:
    path = tmp_path / "embedding.json"
    path.write_text(json.dumps({"provider": provider}))

    selected = load_embedding_preferences(path, defaults=defaults)

    assert selected.provider == provider
    assert selected.omlx == defaults.omlx
    assert selected.openai == defaults.openai


def test_overriding_one_model_leaves_the_other_baseline(tmp_path, defaults) -> None:
    path = tmp_path / "embedding.json"
    path.write_text(json.dumps({"provider": "openai", "openai": {"model": "text-embedding-3-large"}}))

    selected = load_embedding_preferences(path, defaults=defaults)

    assert selected.openai.model == "text-embedding-3-large"
    assert selected.omlx == defaults.omlx


def test_complete_compatible_section_loads(tmp_path, defaults) -> None:
    path = tmp_path / "embedding.json"
    path.write_text(
        json.dumps({"provider": "openai_compatible", "openai_compatible": COMPATIBLE})
    )

    selected = load_embedding_preferences(path, defaults=defaults)

    assert selected.openai_compatible is not None
    assert selected.openai_compatible.api_key_env == "MY_EMBED_KEY"
    assert embedder_identity(selected) == "openai_compatible:house-bge-m3"


def test_a_trailing_slash_is_normalized_away(tmp_path, defaults) -> None:
    path = tmp_path / "embedding.json"
    path.write_text(
        json.dumps(
            {
                "provider": "openai_compatible",
                "openai_compatible": {**COMPATIBLE, "base_url": "https://host.example/v1//"},
            }
        )
    )

    selected = load_embedding_preferences(path, defaults=defaults)

    assert selected.openai_compatible.base_url == "https://host.example/v1"


def test_identity_ignores_the_physical_endpoint(tmp_path, defaults) -> None:
    """Moving one service to a new host must not park its dedup memory."""
    path = tmp_path / "embedding.json"
    identities = []
    for host in ("https://127.0.0.1:8080/v1", "https://host.docker.internal:8080/v1"):
        path.write_text(
            json.dumps(
                {
                    "provider": "openai_compatible",
                    "openai_compatible": {**COMPATIBLE, "base_url": host},
                }
            )
        )
        identities.append(embedder_identity(load_embedding_preferences(path, defaults=defaults)))
    assert identities[0] == identities[1] == "openai_compatible:house-bge-m3"


def test_state_never_holds_a_resolved_credential(tmp_path, defaults) -> None:
    """Only the variable *name* is representable, so no dump can leak a key."""
    path = tmp_path / "embedding.json"
    path.write_text(
        json.dumps({"provider": "openai_compatible", "openai_compatible": COMPATIBLE})
    )

    dumped = load_embedding_preferences(path, defaults=defaults).model_dump_json()

    assert "MY_EMBED_KEY" in dumped
    assert "api_key" not in json.loads(dumped)["openai_compatible"]
    assert set(json.loads(dumped)["openai_compatible"]) == {
        "base_url",
        "model",
        "api_key_env",
        "space_id",
    }


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("not json", id="not-json"),
        pytest.param("[]", id="top-level-array"),
        pytest.param(json.dumps({"provider": "ollama"}), id="unknown-provider"),
        pytest.param(json.dumps({"temperature": 0.4}), id="unknown-key"),
        pytest.param(
            json.dumps({"omlx": {"dim": 512}}), id="unknown-section-key"
        ),
        pytest.param(
            json.dumps({"omlx": {"model": "has spaces"}}), id="bad-model"
        ),
        pytest.param(
            json.dumps({"provider": "openai_compatible"}),
            id="compatible-absent",
        ),
        pytest.param(
            json.dumps({"openai_compatible": {"base_url": "https://host.example/v1"}}),
            id="compatible-partial",
        ),
        pytest.param(
            json.dumps({"openai_compatible": {**COMPATIBLE, "api_key_env": "lower_case"}}),
            id="bad-key-env",
        ),
        pytest.param(
            json.dumps({"openai_compatible": {**COMPATIBLE, "space_id": "has spaces"}}),
            id="bad-space-id",
        ),
        pytest.param(
            json.dumps({"openai_compatible": {**COMPATIBLE, "base_url": "ftp://host.example"}}),
            id="bad-scheme",
        ),
        pytest.param(
            json.dumps({"openai_compatible": {**COMPATIBLE, "base_url": "https:///v1"}}),
            id="no-host",
        ),
        pytest.param(
            json.dumps(
                {"openai_compatible": {**COMPATIBLE, "base_url": "https://user:pw@host.example/v1"}}
            ),
            id="userinfo",
        ),
        pytest.param(
            json.dumps(
                {"openai_compatible": {**COMPATIBLE, "base_url": "https://host.example/v1?key=abc"}}
            ),
            id="query",
        ),
        pytest.param(
            json.dumps(
                {"openai_compatible": {**COMPATIBLE, "base_url": "https://host.example/v1#key"}}
            ),
            id="fragment",
        ),
        pytest.param(
            json.dumps(
                {
                    "openai_compatible": {
                        **COMPATIBLE,
                        "base_url": "https://host.example/v1/embeddings",
                    }
                }
            ),
            id="endpoint-shaped",
        ),
    ],
)
def test_present_invalid_state_fails_loudly(tmp_path, defaults, payload: str) -> None:
    path = tmp_path / "embedding.json"
    path.write_text(payload)

    with pytest.raises(RuntimeError, match="invalid embedding preferences"):
        load_embedding_preferences(path, defaults=defaults)
