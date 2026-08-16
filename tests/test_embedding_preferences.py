from __future__ import annotations

import json

import pytest

from next_signal.core.embedding_preferences import (
    embedder_identity,
    load_embedding_preferences,
)

OMLX = {"base_url": "http://127.0.0.1:8081/v1", "model": "Qwen3-Embedding-0.6B-8bit"}
COMPATIBLE = {
    "base_url": "https://host.example/v1",
    "model": "bge-m3",
    "space_id": "house-bge-m3",
}


def test_absent_state_selects_nothing(tmp_path) -> None:
    selected = load_embedding_preferences(tmp_path / "missing.json")

    assert selected.provider is None
    assert selected.selected is False
    assert embedder_identity(selected) is None
    # No section is invented either — prefill belongs to the form, not here.
    assert selected.omlx is None
    assert selected.openai is None
    assert selected.openai_compatible is None


def test_a_saved_section_without_a_selection_stays_unselected(tmp_path) -> None:
    """Configuring a provider is not the same act as choosing it."""
    path = tmp_path / "embedding.json"
    path.write_text(json.dumps({"omlx": OMLX}))

    selected = load_embedding_preferences(path)

    assert selected.selected is False
    assert selected.omlx is not None


@pytest.mark.parametrize(
    ("provider", "section"),
    [("omlx", OMLX), ("openai", {"model": "text-embedding-3-large"})],
)
def test_a_complete_section_can_be_selected(tmp_path, provider: str, section: dict) -> None:
    path = tmp_path / "embedding.json"
    path.write_text(json.dumps({"provider": provider, provider: section}))

    selected = load_embedding_preferences(path)

    assert selected.provider == provider
    assert selected.selected is True


def test_omlx_carries_its_own_endpoint(tmp_path) -> None:
    """Separate from the engine's: one mlx-lm process serves one model."""
    path = tmp_path / "embedding.json"
    path.write_text(json.dumps({"provider": "omlx", "omlx": OMLX}))

    selected = load_embedding_preferences(path)

    assert selected.omlx.base_url == "http://127.0.0.1:8081/v1"
    assert embedder_identity(selected) == "omlx:Qwen3-Embedding-0.6B-8bit"


def test_complete_compatible_section_loads(tmp_path) -> None:
    path = tmp_path / "embedding.json"
    path.write_text(
        json.dumps({"provider": "openai_compatible", "openai_compatible": COMPATIBLE})
    )

    selected = load_embedding_preferences(path)

    assert selected.openai_compatible is not None
    assert embedder_identity(selected) == "openai_compatible:house-bge-m3"


def test_a_trailing_slash_is_normalized_away(tmp_path) -> None:
    path = tmp_path / "embedding.json"
    path.write_text(
        json.dumps(
            {
                "provider": "openai_compatible",
                "openai_compatible": {**COMPATIBLE, "base_url": "https://host.example/v1//"},
            }
        )
    )

    selected = load_embedding_preferences(path)

    assert selected.openai_compatible.base_url == "https://host.example/v1"


def test_identity_ignores_the_physical_endpoint(tmp_path) -> None:
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
        identities.append(embedder_identity(load_embedding_preferences(path)))
    assert identities[0] == identities[1] == "openai_compatible:house-bge-m3"


def test_state_cannot_name_or_hold_a_credential(tmp_path) -> None:
    """Each provider's key has a fixed name, so state references none at all."""
    path = tmp_path / "embedding.json"
    path.write_text(
        json.dumps({"provider": "openai_compatible", "openai_compatible": COMPATIBLE})
    )

    dumped = json.loads(load_embedding_preferences(path).model_dump_json())

    assert set(dumped["openai_compatible"]) == {"base_url", "model", "space_id"}


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("not json", id="not-json"),
        pytest.param("[]", id="top-level-array"),
        pytest.param(json.dumps({"provider": "ollama"}), id="unknown-provider"),
        pytest.param(json.dumps({"temperature": 0.4}), id="unknown-key"),
        pytest.param(json.dumps({"omlx": {**OMLX, "dim": 512}}), id="unknown-section-key"),
        pytest.param(json.dumps({"omlx": {**OMLX, "model": "has spaces"}}), id="bad-model"),
        pytest.param(
            json.dumps({"openai_compatible": {**COMPATIBLE, "api_key_env": "MY_KEY"}}),
            id="api-key-env-is-gone",
        ),
        pytest.param(json.dumps({"provider": "omlx"}), id="omlx-absent"),
        pytest.param(json.dumps({"omlx": {"model": "bge-m3"}}), id="omlx-no-endpoint"),
        pytest.param(
            json.dumps({"provider": "openai_compatible"}),
            id="compatible-absent",
        ),
        pytest.param(
            json.dumps({"openai_compatible": {"base_url": "https://host.example/v1"}}),
            id="compatible-partial",
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
        pytest.param(
            json.dumps({"omlx": {**OMLX, "base_url": "https://user:pw@host/v1"}}),
            id="omlx-userinfo",
        ),
    ],
)
def test_present_invalid_state_fails_loudly(tmp_path, payload: str) -> None:
    path = tmp_path / "embedding.json"
    path.write_text(payload)

    with pytest.raises(RuntimeError, match="invalid embedding preferences"):
        load_embedding_preferences(path)
