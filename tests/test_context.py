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
