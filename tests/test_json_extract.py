"""Coverage for the JSON-leak salvage. Mirrors the cases that historically
broke the agno-browser-mlx browser-use loop with Qwen3 outputs.
"""

from __future__ import annotations

import json

import pytest

from paca.tools._json_extract import extract_json_object


@pytest.mark.parametrize(
    "raw, expect_keys",
    [
        ('{"a": 1, "b": 2}', {"a", "b"}),
        ('  {"a": 1}  ', {"a"}),
        ('<thinking>blah</thinking>{"action": "click", "x": 10}', {"action", "x"}),
        ('```json\n{"k": "v"}\n```', {"k"}),
        ('```\n{"k": "v"}\n```', {"k"}),
        ('preamble text {"k": "v"} trailing', {"k"}),
        ('<action>{"nested": {"a": 1}}</action>', {"nested"}),
        # Nested braces inside thinking should not confuse the picker:
        ('<thinking>maybe {bait: 1}</thinking>{"real": true}', {"real"}),
        # String with brace inside should not break depth tracking:
        ('{"text": "look: { not real }", "ok": true}', {"text", "ok"}),
    ],
)
def test_extracts_valid_json(raw: str, expect_keys: set[str]) -> None:
    out = extract_json_object(raw)
    parsed = json.loads(out)
    assert set(parsed.keys()) == expect_keys


def test_passthrough_when_no_object() -> None:
    assert extract_json_object("no json here") == "no json here"


def test_empty_input() -> None:
    assert extract_json_object("") == ""


def test_picks_largest_object() -> None:
    raw = '{"small": 1} junk {"bigger": {"x": 1, "y": 2}}'
    out = extract_json_object(raw)
    parsed = json.loads(out)
    assert "bigger" in parsed
