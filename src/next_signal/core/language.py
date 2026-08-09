"""Per-agent output-language policy resolution.

Split out of ``core.context`` (which stays scoped to the static shared-context
block) because this module owns a live resolution chain: a runtime preference
file the dashboard can write, a hardcoded fallback, and per-call overrides for
policies that can't be resolved from any static source.

Four policies, declared per-agent via ``extra.output_language``:

- ``"off"``            -- no rule ever.
- ``"global"``         -- resolved from the live preference file
  (``LANGUAGE_STATE_FILE``), falling back to ``DEFAULT_LANGUAGE``. Never reads
  ``.env`` -- an env var can't be changed by the dashboard without a container
  restart, so the live value lives in the state file instead.
- ``"same_as_source"`` -- resolved from a caller-supplied ``override``; raises
  if none is given, since a global default has no idea what one specific
  item's source language is.
- ``"fixed:<lang>"``   -- a literal, e.g. ``"fixed:en"``.

A bare ``False`` in YAML still means ``"off"``, for back-compat with configs
written before this policy model existed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from next_signal.core.paths import STATE_ROOT

# Recognized values -> the name used inside the generated rule.
_LANG_NAMES = {"zh": "Simplified Chinese", "en": "English"}

# Bottom of the `global` fallback chain. A fresh `.env` -- with or without a
# language field -- can never leave the system unconfigured, because `.env`
# is not part of this resolution at all. Matches the dashboard's own
# DEFAULT_LOCALE (dashboard/lib/i18n/dictionaries.ts) for consistency.
DEFAULT_LANGUAGE = "en"

LANGUAGE_STATE_FILE = STATE_ROOT / "language.json"

# A prompt that names the language itself substitutes this token in place, so
# the rule sits where its author put it and the prompt's own closing contract
# ("Return JSON", "Do NOT pad") stays last.
LANGUAGE_TOKEN = "{{OUTPUT_LANGUAGE}}"


def language_name(lang: str) -> str:
    """Display name substituted into a prompt's own language sentence."""
    return _LANG_NAMES[lang]


def language_rule(lang: str) -> str:
    """Fallback block for prompts with no ``{{OUTPUT_LANGUAGE}}`` token.

    Unconditional, and names field *classes* rather than field names -- both
    measured choices; see the archived ``configurable-output-language``
    change's design.md D4/D5. This wording is unchanged by the policy
    generalization -- only the source of ``lang`` changed.
    """
    name = _LANG_NAMES[lang]
    return (
        "## Output language\n\n"
        f"Write every prose field of your output in {name}, regardless of the "
        "language of the input you are given. This does not depend on the "
        "language of the goals, the article body, or the source document.\n\n"
        "Identifier-like fields -- tags, slugs, category paths -- stay lowercase "
        "English. Keep proper nouns (company, model, repository, paper and "
        "benchmark names) in their original form."
    )


def _read_preference_file() -> str | None:
    """Read the live 'global' preference, or ``None`` if unset/absent.

    Read at call time, never cached, so a dashboard write takes effect on the
    next agent build with no reload needed. Absence is a valid, permanent
    state -- "nobody has touched the dashboard control yet" -- not an error.
    """
    if not LANGUAGE_STATE_FILE.exists():
        return None
    try:
        data = json.loads(LANGUAGE_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{LANGUAGE_STATE_FILE} is corrupt: {exc}") from exc
    lang = str(data.get("content_language", "")).strip().lower()
    if not lang:
        return None
    if lang not in _LANG_NAMES:
        raise RuntimeError(
            f"{LANGUAGE_STATE_FILE}: content_language={lang!r} is not recognized; "
            f"expected one of {', '.join(sorted(_LANG_NAMES))}"
        )
    return lang


def global_language() -> str:
    """Resolve the ``global`` policy: preference file, else the hardcoded default."""
    return _read_preference_file() or DEFAULT_LANGUAGE


def set_global_language(lang: str, *, updated_by: str = "dashboard") -> None:
    """Write the live preference file atomically (temp file + rename)."""
    if lang not in _LANG_NAMES:
        raise RuntimeError(
            f"unrecognized language {lang!r}; expected one of {', '.join(sorted(_LANG_NAMES))}"
        )
    LANGUAGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "content_language": lang,
        "updated_at": datetime.now(UTC).isoformat(),
        "updated_by": updated_by,
    }
    tmp = LANGUAGE_STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(LANGUAGE_STATE_FILE)


def normalize_policy(raw: object) -> str:
    """Normalize a YAML ``extra.output_language`` value to a policy string.

    Back-compat: the bare booleans agent configs shipped before this policy
    model existed still resolve the same way (``False`` -> ``"off"``,
    ``True`` -> ``"global"``, same as the prior default-on behavior).
    """
    if raw is False:
        return "off"
    if raw is True:
        return "global"
    if isinstance(raw, str):
        return raw
    raise RuntimeError(f"invalid output_language policy: {raw!r}")


def resolve_language(policy: str, *, override: str | None = None) -> str | None:
    """Resolve an agent's declared policy to a concrete language, or ``None`` for 'off'."""
    if policy == "off":
        return None
    if policy == "global":
        return global_language()
    if policy == "same_as_source":
        if not override:
            raise RuntimeError(
                "policy 'same_as_source' requires a caller-supplied `language=` override"
            )
        return override
    if policy.startswith("fixed:"):
        return policy.removeprefix("fixed:")
    raise RuntimeError(f"unrecognized language policy: {policy!r}")
