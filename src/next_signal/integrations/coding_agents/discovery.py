"""Call-time discovery for optional coding-agent executables."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

from next_signal.integrations.coding_agents.types import ProviderName

_BINARY_ENV: dict[ProviderName, str] = {
    "codex": "CODEX_BIN",
    "claude": "CLAUDE_BIN",
}


def resolve_executable(provider: ProviderName) -> str:
    env_name = _BINARY_ENV[provider]
    configured = os.environ.get(env_name, "").strip()
    if configured:
        expanded = str(Path(configured).expanduser())
        found = shutil.which(expanded)
        if not found:
            raise RuntimeError(
                f"{provider} CLI not found at {configured!r}; fix {env_name} or install {provider}"
            )
        return found

    found = shutil.which(provider)
    if not found:
        raise RuntimeError(
            f"{provider} CLI not found on PATH; install {provider} or set {env_name}"
        )
    return found


def binary_env_name(provider: ProviderName) -> str:
    return _BINARY_ENV[provider]
