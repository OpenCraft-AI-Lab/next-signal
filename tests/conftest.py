"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from next_signal.core import secrets


@pytest.fixture(autouse=True)
def isolated_credential_store(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point the credential store at a per-test temp file.

    Autouse and unconditional: without it a test would read the developer's real
    ``~/.next-signal/secrets.json``, so a suite could pass only on a machine that
    happens to have credentials configured — or, worse, spend money against them.
    Tests that need a credential write it through ``secrets.save_secret``.
    """
    store = tmp_path_factory.mktemp("secrets") / "secrets.json"
    monkeypatch.setattr(secrets, "SECRETS_FILE", store)
    return store
