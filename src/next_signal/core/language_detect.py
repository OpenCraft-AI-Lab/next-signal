"""Deterministic source-language detection for the ``same_as_source`` policy.

Not an LLM call, deliberately: using a model to decide *which* language to
target would reintroduce the same sampling-variance failure this whole
mechanism exists to fix (``knowledge_frontmatter`` with no rule at all
measured 17.9%/7.7% of titles/summaries in the wrong language, the same
article flipping between repeat runs on identical input -- see the archived
``configurable-output-language`` change and ``output-language-policy``
design.md D6). A classical, deterministic classifier has no sampling step to
be unreliable in.

Scope is deliberately narrow: the rest of the system only recognizes ``zh``
and ``en`` (``next_signal.core.language._LANG_NAMES``), so a Unicode-script-ratio
heuristic is close to the ceiling for this problem. If a third language is
ever added, replace ``detect_language`` here -- callers only depend on this
function's signature, not its internals.
"""

from __future__ import annotations

# CJK Unified Ideographs, the range that matters for zh vs. en at this scope.
# (Deliberately not chasing Hangul/Kana/extension blocks -- not a language the
# rest of the system recognizes yet.)
_CJK_LOW = 0x4E00
_CJK_HIGH = 0x9FFF

# Below this ratio of CJK-to-alphabetic characters, text is classified `en`.
# Chosen so a handful of Chinese proper nouns in an English text (or vice
# versa) doesn't flip the classification -- see design.md's threshold-tuning
# note in Risks/Trade-offs.
_CJK_RATIO_THRESHOLD = 0.15


def detect_language(text: str) -> str:
    """Classify ``text`` as ``"zh"`` or ``"en"``, deterministically.

    The same input always produces the same output -- no sampling, no network
    call, no model. Text with no alphabetic signal at all (empty string, pure
    code/punctuation) falls back to ``"en"``, the same hardcoded default the
    ``global`` policy uses when nothing else is configured.
    """
    cjk = sum(1 for ch in text if _CJK_LOW <= ord(ch) <= _CJK_HIGH)
    letters = sum(1 for ch in text if ch.isalpha())
    if letters == 0:
        return "en"
    return "zh" if (cjk / letters) > _CJK_RATIO_THRESHOLD else "en"
