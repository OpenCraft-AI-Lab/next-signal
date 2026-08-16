"""Centralized OMLX endpoint resolution for the local *chat* model.

Both halves come from the shared state volume: ``base_url`` from the engine
preferences the settings page writes, the API key from the credential store.
Neither is read from the environment, so an operator who starts a local server
points next-signal at it in the browser rather than by editing ``.env`` and
recreating a container.

The embedding capability owns its own OMLX endpoint in ``embedding.json``: one
mlx-lm process serves one model, so a chat model and an embedding model are two
addresses.
"""

from __future__ import annotations

from next_signal.core.secrets import get_secret


def resolve_omlx_endpoint(*, base_url: str | None = None) -> dict[str, str]:
    """Return the selected OMLX base URL and API key.

    ``base_url`` is an explicit runtime override — a production stage passing
    the endpoint its own job already resolved. Otherwise the engine preferences
    are authoritative.
    """
    if base_url is not None:
        selected = base_url.strip()
    else:
        # Imported here rather than at module scope: engine preferences are read
        # at call time, and a module-level import would make this file's import
        # order matter to a settings read.
        from next_signal.core.engine_preferences import load_engine_preferences

        selected = (load_engine_preferences().omlx.base_url or "").strip()
    if not selected:
        raise RuntimeError(
            "No local OMLX endpoint is configured. Set it on the dashboard "
            "settings page (Settings -> Engine), or use a non-omlx model profile."
        )
    # Optional: a local OMLX server usually has no key at all.
    return {
        "base_url": selected,
        "api_key": get_secret("OMLX_API_KEY"),
    }
