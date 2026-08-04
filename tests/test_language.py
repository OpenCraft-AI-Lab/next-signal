"""Coverage for the per-agent language-policy resolver (paca.core.language).

Split out of test_context.py alongside the module split: shared static
context and language-policy resolution used to live in the same module, but
the policy resolver grew a live preference file, per-call overrides, and a
hardcoded fallback — enough surface to warrant its own test module.
"""

from __future__ import annotations

import json

import pytest

from paca.core import language as lang


@pytest.fixture(autouse=True)
def _isolate_state_file(tmp_path, monkeypatch):
    """Point the preference file at a scratch path so tests never touch the
    real `~/.next-signal/language.json` a developer or CI box might have."""
    monkeypatch.setattr(lang, "LANGUAGE_STATE_FILE", tmp_path / "language.json")
    yield


# ---------------------------------------------------------------------------
# global_language() / the preference file
# ---------------------------------------------------------------------------


def test_global_language_falls_back_when_file_missing() -> None:
    assert not lang.LANGUAGE_STATE_FILE.exists()
    assert lang.global_language() == lang.DEFAULT_LANGUAGE


def test_global_language_reads_the_file() -> None:
    lang.set_global_language("zh")
    assert lang.global_language() == "zh"


def test_global_language_is_read_per_call() -> None:
    """Call-time read: a later write must take effect without any reload()."""
    lang.set_global_language("zh")
    assert lang.global_language() == "zh"
    lang.set_global_language("en")
    assert lang.global_language() == "en"


def test_set_global_language_rejects_unrecognized_value() -> None:
    with pytest.raises(RuntimeError, match="fr"):
        lang.set_global_language("fr")
    assert not lang.LANGUAGE_STATE_FILE.exists()


def test_set_global_language_writes_atomically_no_tmp_left_behind() -> None:
    lang.set_global_language("zh")
    assert lang.LANGUAGE_STATE_FILE.exists()
    assert not lang.LANGUAGE_STATE_FILE.with_suffix(".tmp").exists()


def test_preference_file_corrupt_json_raises() -> None:
    lang.LANGUAGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lang.LANGUAGE_STATE_FILE.write_text("not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="corrupt"):
        lang.global_language()


def test_preference_file_unrecognized_value_raises() -> None:
    lang.LANGUAGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lang.LANGUAGE_STATE_FILE.write_text(
        json.dumps({"content_language": "fr"}), encoding="utf-8"
    )
    with pytest.raises(RuntimeError) as e:
        lang.global_language()
    assert "fr" in str(e.value)
    assert "zh" in str(e.value) and "en" in str(e.value)


def test_preference_file_blank_value_falls_back() -> None:
    """An empty content_language is 'unset', not a validation error."""
    lang.LANGUAGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lang.LANGUAGE_STATE_FILE.write_text(
        json.dumps({"content_language": "  "}), encoding="utf-8"
    )
    assert lang.global_language() == lang.DEFAULT_LANGUAGE


# ---------------------------------------------------------------------------
# normalize_policy()
# ---------------------------------------------------------------------------


def test_normalize_policy_bool_backcompat() -> None:
    assert lang.normalize_policy(False) == "off"
    assert lang.normalize_policy(True) == "global"


def test_normalize_policy_passes_strings_through() -> None:
    assert lang.normalize_policy("same_as_source") == "same_as_source"
    assert lang.normalize_policy("fixed:en") == "fixed:en"
    assert lang.normalize_policy("global") == "global"


def test_normalize_policy_rejects_garbage() -> None:
    with pytest.raises(RuntimeError):
        lang.normalize_policy(42)


# ---------------------------------------------------------------------------
# resolve_language()
# ---------------------------------------------------------------------------


def test_resolve_off_is_none_and_never_touches_the_file() -> None:
    lang.LANGUAGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lang.LANGUAGE_STATE_FILE.write_text("not json", encoding="utf-8")  # would raise if read
    assert lang.resolve_language("off") is None


def test_resolve_global_reads_the_live_preference() -> None:
    lang.set_global_language("zh")
    assert lang.resolve_language("global") == "zh"


def test_resolve_same_as_source_requires_override() -> None:
    with pytest.raises(RuntimeError, match="same_as_source"):
        lang.resolve_language("same_as_source")


def test_resolve_same_as_source_uses_override_not_the_global_file() -> None:
    lang.set_global_language("en")
    assert lang.resolve_language("same_as_source", override="zh") == "zh"


def test_resolve_fixed_literal() -> None:
    assert lang.resolve_language("fixed:en") == "en"
    assert lang.resolve_language("fixed:zh") == "zh"


def test_resolve_unrecognized_policy_raises() -> None:
    with pytest.raises(RuntimeError, match="bogus"):
        lang.resolve_language("bogus")


# ---------------------------------------------------------------------------
# language_rule() / language_name() — unchanged wording, moved module
# ---------------------------------------------------------------------------


def test_language_rule_is_unconditional() -> None:
    """The conditional phrasing is the measured cause of the drift this rule fixes."""
    rule = lang.language_rule("zh")
    assert "Simplified Chinese" in rule
    assert "regardless of" in rule
    for hedge in ("if the goals", "otherwise English", "match the language"):
        assert hedge.lower() not in rule.lower()


def test_language_rule_exempts_identifiers() -> None:
    """Tags are dropped by _normalize_tags if they contain CJK — never translate them."""
    for code in ("zh", "en"):
        rule = lang.language_rule(code)
        assert "tags" in rule
        assert "lowercase" in rule
        assert "proper nouns" in rule


def test_language_name() -> None:
    assert lang.language_name("en") == "English"
    assert lang.language_name("zh") == "Simplified Chinese"
