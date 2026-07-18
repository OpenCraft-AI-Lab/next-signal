"""Salvage JSON from local-LLM responses that wrap output in tags or prose.

Ported from agno-browser-mlx. Used by the browser-use tool wrapper to keep
Qwen3 responses parseable even when they include ``<thinking>`` / ``<action>``
fences or markdown code blocks. Small, dependency-free, well-tested in
``tests/test_json_extract.py``.
"""

from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_TAG_RE = re.compile(r"<(?:thinking|action|agent_output|json)>(.*?)</[^>]+>", re.DOTALL | re.IGNORECASE)


def extract_json_object(text: str) -> str:
    """Return the largest balanced ``{...}`` JSON object found in ``text``.

    Strategy (cheapest first):
      1. If the text parses as JSON already, return it stripped.
      2. Strip wrapping tags and code fences, then scan for the largest
         balanced brace span and return that slice.

    Returns the original text unchanged if no candidate is found — the caller
    decides whether to fail or pass through.
    """
    if not text:
        return text

    s = text.strip()
    try:
        json.loads(s)
        return s
    except ValueError:
        pass

    # Drop tag wrappers that often hide the real payload.
    cleaned = _TAG_RE.sub(lambda m: m.group(1), s)
    # Prefer fenced JSON blocks if any.
    fences = _FENCE_RE.findall(cleaned)
    candidates = [c.strip() for c in fences] + [cleaned]

    best: str | None = None
    for cand in candidates:
        span = _largest_balanced_object(cand)
        if span and (best is None or len(span) > len(best)):
            best = span

    return best if best is not None else text


def _largest_balanced_object(text: str) -> str | None:
    best_start = -1
    best_end = -1
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                if (i - start) > (best_end - best_start):
                    best_start, best_end = start, i
                start = -1
    if best_start >= 0 and best_end > best_start:
        return text[best_start : best_end + 1]
    return None
