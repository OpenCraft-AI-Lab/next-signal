"""Centralized OMLX endpoint resolution."""

from __future__ import annotations

import os


def resolve_omlx_endpoint(
    *,
    base_url: str | None = None,
    default_base_url: str | None = None,
) -> dict[str, str]:
    """Return the selected OMLX base URL and API key.

    ``base_url`` is an explicit runtime override. Otherwise the environment is
    authoritative; ``default_base_url`` is only for fresh-install settings
    whose persisted value must be usable before an environment is configured.
    """
    if base_url is not None:
        selected = base_url.strip()
    else:
        selected = os.environ.get("OMLX_BASE_URL", "").strip()
        if not selected and default_base_url is not None:
            selected = default_base_url.strip()
    if not selected:
        raise RuntimeError(
            "OMLX_BASE_URL not set. Either set OMLX_BASE_URL (and OMLX_API_KEY) "
            "in .env, or use a non-omlx model profile."
        )
    return {
        "base_url": selected,
        "api_key": os.environ.get("OMLX_API_KEY", ""),
    }
