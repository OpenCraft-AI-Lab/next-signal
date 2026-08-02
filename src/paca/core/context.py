"""Shared static context and the output-language setting the loader applies to
an agent's instructions.

Pattern borrowed from agno-agi/investment-team (`context/loader.py`). The
files are read once at module-import time and cached; the dashboard's
hot-reload path can call ``reload()`` to pick up edits without restarting
the process.

Filenames sort lexicographically — prefix with two-digit numbers
(``00_house_rules.md``, ``10_user_profile.md``) to control the order.
Files starting with ``_`` are skipped, so you can stash drafts.

``SIGNAL_OUTPUT_LANG`` lives here rather than in ``config.py`` because that
module is the YAML→Pydantic loader, and because the rule this setting produces
is prompt context — the same kind of thing as the shared block. Only the static
files are cached; the language is re-read per call so a changed environment
takes effect without a ``reload()``.
"""

from __future__ import annotations

import os

from paca.core.paths import PROMPTS_DIR

SHARED_DIR = PROMPTS_DIR / "_shared"

_cached: str | None = None

# Env var name deliberately avoids the ``PACA_`` prefix, per the project's
# convention for new domain-named variables.
OUTPUT_LANG_ENV = "SIGNAL_OUTPUT_LANG"

# Recognized values → the name used inside the generated rule.
_LANG_NAMES = {"zh": "Simplified Chinese", "en": "English"}

# Language the prompts were written against, used when the env var is unset so
# a prompt carrying the token still reads as a complete sentence.
DEFAULT_LANG = "zh"

# A prompt that names the language itself substitutes this token in place, so
# the rule sits where its author put it and the prompt's own closing contract
# ("Return JSON", "Do NOT pad") stays last. Whether that beats appending the
# rule is NOT measured — see design.md D1, where position was blamed twice for a
# regression that turned out to be an unrelated heading.
LANGUAGE_TOKEN = "{{OUTPUT_LANGUAGE}}"


def shared_context() -> str:
    """Return the concatenated shared-context string. Cached after first call."""
    global _cached
    if _cached is None:
        _cached = _load()
    return _cached


def reload() -> str:
    """Force re-read from disk. Called by the dashboard hot-reload hook."""
    global _cached
    _cached = _load()
    return _cached


def _load() -> str:
    if not SHARED_DIR.exists():
        return ""
    sections: list[str] = []
    for path in sorted(SHARED_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue
        sections.append(path.read_text(encoding="utf-8").rstrip())
    return "\n\n---\n\n".join(sections)


def output_language() -> str | None:
    """Resolve ``SIGNAL_OUTPUT_LANG``, or ``None`` when it is unset.

    Read at call time, never at import, so a missing value can't break startup
    and a changed value takes effect on the next agent build. An unrecognized
    value raises rather than defaulting — a silent fallback would ship the
    wrong language into the wiki without anyone noticing.
    """
    raw = os.environ.get(OUTPUT_LANG_ENV, "").strip()
    if not raw:
        return None
    lang = raw.lower()
    if lang not in _LANG_NAMES:
        raise RuntimeError(
            f"{OUTPUT_LANG_ENV}={raw!r} is not recognized; "
            f"expected one of {', '.join(sorted(_LANG_NAMES))}"
        )
    return lang


def language_name(lang: str | None) -> str:
    """Display name substituted into a prompt's own language sentence."""
    return _LANG_NAMES[lang or DEFAULT_LANG]


def language_rule(lang: str) -> str:
    """Fallback block for prompts with no ``{{OUTPUT_LANGUAGE}}`` token.

    Unconditional, and names field *classes* rather than field names — both
    measured choices, see design.md D4/D5.
    """
    name = _LANG_NAMES[lang]
    return (
        "## Output language\n\n"
        f"Write every prose field of your output in {name}, regardless of the "
        "language of the input you are given. This does not depend on the "
        "language of the goals, the article body, or the source document.\n\n"
        "Identifier-like fields — tags, slugs, category paths — stay lowercase "
        "English. Keep proper nouns (company, model, repository, paper and "
        "benchmark names) in their original form."
    )
