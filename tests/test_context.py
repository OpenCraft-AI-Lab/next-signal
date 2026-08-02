"""Coverage for the shared-context loader.

The loader concatenates ``prompts/_shared/*.md`` (skipping anything that
starts with ``_``) and is wired into the agent loader so every agent picks
up the rules without per-config repetition.
"""

from __future__ import annotations

import pytest

from paca.core import context as ctx


@pytest.fixture(autouse=True)
def _reset_cache():
    """Force every test to re-read from disk so cache state doesn't leak."""
    ctx._cached = None
    yield
    ctx._cached = None


def test_loads_shipped_shared_files() -> None:
    out = ctx.shared_context()
    # Files committed at /prompts/_shared/00_house_rules.md and 10_user_profile.md
    assert "House rules" in out
    assert "User profile" in out


def test_files_separated_by_horizontal_rule() -> None:
    out = ctx.shared_context()
    # Each file gets joined by a markdown horizontal rule.
    assert "\n\n---\n\n" in out


def test_skip_leading_underscore(tmp_path, monkeypatch) -> None:
    """Files starting with ``_`` are drafts and must not leak into the output."""
    monkeypatch.setattr(ctx, "SHARED_DIR", tmp_path)
    (tmp_path / "00_real.md").write_text("REAL CONTENT")
    (tmp_path / "_draft.md").write_text("DRAFT CONTENT — DO NOT INJECT")
    out = ctx.reload()
    assert "REAL CONTENT" in out
    assert "DRAFT" not in out


def test_missing_dir_returns_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ctx, "SHARED_DIR", tmp_path / "does-not-exist")
    assert ctx.reload() == ""


def test_reload_picks_up_changes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ctx, "SHARED_DIR", tmp_path)
    f = tmp_path / "00_x.md"
    f.write_text("v1")
    assert "v1" in ctx.reload()
    f.write_text("v2")
    assert "v2" in ctx.reload()


# ---------------------------------------------------------------------------
# Output language (SIGNAL_OUTPUT_LANG)
# ---------------------------------------------------------------------------


def test_output_language_unset_is_none(monkeypatch) -> None:
    monkeypatch.delenv(ctx.OUTPUT_LANG_ENV, raising=False)
    assert ctx.output_language() is None


def test_output_language_blank_is_none(monkeypatch) -> None:
    """An empty value is 'unset', not a validation error — .env files ship blanks."""
    monkeypatch.setenv(ctx.OUTPUT_LANG_ENV, "   ")
    assert ctx.output_language() is None


@pytest.mark.parametrize("raw,expected", [("zh", "zh"), ("en", "en"), ("ZH", "zh")])
def test_output_language_recognized(monkeypatch, raw, expected) -> None:
    monkeypatch.setenv(ctx.OUTPUT_LANG_ENV, raw)
    assert ctx.output_language() == expected


def test_output_language_unrecognized_raises(monkeypatch) -> None:
    monkeypatch.setenv(ctx.OUTPUT_LANG_ENV, "fr")
    with pytest.raises(RuntimeError) as e:
        ctx.output_language()
    # Must name the offending value and the accepted set, not just "invalid".
    assert "fr" in str(e.value)
    assert "zh" in str(e.value) and "en" in str(e.value)


def test_output_language_is_read_per_call(monkeypatch) -> None:
    """Call-time read: changing the env must take effect without reload()."""
    monkeypatch.setenv(ctx.OUTPUT_LANG_ENV, "zh")
    assert ctx.output_language() == "zh"
    monkeypatch.setenv(ctx.OUTPUT_LANG_ENV, "en")
    assert ctx.output_language() == "en"


def test_language_rule_is_unconditional() -> None:
    """The conditional phrasing is the measured cause of the drift being fixed."""
    rule = ctx.language_rule("zh")
    assert "Simplified Chinese" in rule
    assert "regardless of" in rule
    for hedge in ("if the goals", "otherwise English", "match the language"):
        assert hedge.lower() not in rule.lower()


def test_language_rule_exempts_identifiers() -> None:
    """Tags are dropped by _normalize_tags if they contain CJK — never translate them."""
    for lang in ("zh", "en"):
        rule = ctx.language_rule(lang)
        assert "tags" in rule
        assert "lowercase" in rule
        assert "proper nouns" in rule


def test_language_name_defaults_when_unset() -> None:
    """A prompt carrying the token must still read as a sentence with no env var."""
    assert ctx.language_name(None) == ctx.language_name(ctx.DEFAULT_LANG)
    assert ctx.language_name("en") == "English"
