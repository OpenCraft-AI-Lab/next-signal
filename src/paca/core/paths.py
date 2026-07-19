"""Standard filesystem paths used across the framework."""

from __future__ import annotations

import os
from pathlib import Path

# Project root — resolved from this file's location, not CWD, so it works
# regardless of where commands are invoked from (CLI, dashboard child, tests).
PROJECT_ROOT = Path(__file__).resolve().parents[3]

CONFIGS_DIR = PROJECT_ROOT / "configs"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# User-state root (overridable for tests via env var).
STATE_ROOT = Path(os.environ.get("PACA_STATE_DIR", Path.home() / ".next-signal"))

KNOWLEDGE_DIR = STATE_ROOT / "knowledge"
AGENT_TMP_DIR = Path(os.environ.get("PACA_AGENT_TMP_DIR", STATE_ROOT / "agent-tmp"))
LOGS_DIR = Path.home() / "Library" / "Logs" / "next-signal"

# WIKI_DIR / WIKI_RAW_DIR resolve from env lazily (PEP 562) so a missing path
# fails loud the first time it's actually used, not at import — `.env` is
# loaded after this module imports, and tests inject via monkeypatch.setenv.
_WIKI_ENV = {"WIKI_DIR": "PACA_WIKI_DIR", "WIKI_RAW_DIR": "PACA_WIKI_RAW_DIR"}


def __getattr__(name: str) -> Path:
    env_name = _WIKI_ENV.get(name)
    if env_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise RuntimeError(f"{env_name} is required; set it in .env (see .env.example)")
    return Path(value)


def ensure_dirs() -> None:
    """Create all standard directories if missing. Safe to call repeatedly."""
    for d in (STATE_ROOT, KNOWLEDGE_DIR, AGENT_TMP_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
