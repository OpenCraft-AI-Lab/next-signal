from __future__ import annotations

import pytest

from paca.agents import loader
from paca.core.config import AgentConfig


def test_build_db_free_agent_does_not_touch_db(monkeypatch) -> None:
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.name = kwargs["name"]

    monkeypatch.setattr(loader, "Agent", FakeAgent)
    monkeypatch.setattr(loader, "get_model", lambda name: f"model:{name}")
    monkeypatch.setattr(loader, "resolve_tools", lambda names: [])
    monkeypatch.setattr(
        loader,
        "get_db",
        lambda: (_ for _ in ()).throw(AssertionError("db should not be built")),
    )

    agent = loader.build_from_config(
        AgentConfig(
            name="knowledge_artifact_editor",
            model_profile="local",
            instructions="Return JSON only.",
            markdown=False,
            add_history_to_context=False,
            extra={"db": False, "shared_context": False},
        )
    )

    assert agent.name == "knowledge_artifact_editor"
    assert "db" not in captured



# ---------------------------------------------------------------------------
# Instruction composition: shared context + output-language delivery
# ---------------------------------------------------------------------------


def _compose(monkeypatch, *, instructions, extra, lang="zh", shared="HOUSE RULES BLOCK"):
    monkeypatch.setattr(loader, "shared_context", lambda: shared)
    monkeypatch.setattr(loader, "output_language", lambda: lang)
    return loader._compose_instructions(
        AgentConfig(
            name="probe",
            model_profile="local",
            instructions=instructions,
            markdown=False,
            add_history_to_context=False,
            extra=extra,
        )
    )


_WITH_TOKEN = "Write summary in {{OUTPUT_LANGUAGE}}.\nReturn JSON. No fences."
_NO_TOKEN = "AGENT OWN PROMPT"


def test_token_is_substituted_in_place(monkeypatch) -> None:
    """The measured position: the prompt's own closer must still land last."""
    out = _compose(monkeypatch, instructions=_WITH_TOKEN, extra={"shared_context": False})
    assert "Write summary in Simplified Chinese." in out
    assert "{{OUTPUT_LANGUAGE}}" not in out
    # No appended block, and the prompt's closing contract is the final line.
    assert "## Output language" not in out
    assert out.strip().endswith("Return JSON. No fences.")


def test_english_target_substitutes_english(monkeypatch) -> None:
    out = _compose(monkeypatch, instructions=_WITH_TOKEN, extra={}, lang="en")
    assert "Write summary in English." in out


def test_unset_language_still_substitutes_a_default(monkeypatch) -> None:
    """A prompt carrying the token must read as a sentence even when unset."""
    out = _compose(monkeypatch, instructions=_WITH_TOKEN, extra={}, lang=None)
    assert "Write summary in Simplified Chinese." in out
    assert "{{OUTPUT_LANGUAGE}}" not in out


def test_prompt_without_token_gets_appended_block(monkeypatch) -> None:
    """Unmigrated prompts still receive the rule rather than silently missing it."""
    out = _compose(monkeypatch, instructions=_NO_TOKEN, extra={"shared_context": False})
    assert "## Output language" in out
    assert out.index(_NO_TOKEN) < out.index("## Output language")


def test_unset_language_appends_nothing_without_token(monkeypatch) -> None:
    out = _compose(monkeypatch, instructions=_NO_TOKEN, extra={}, lang=None)
    assert "## Output language" not in out


def test_agent_instructions_come_before_shared_block(monkeypatch) -> None:
    out = _compose(monkeypatch, instructions=_NO_TOKEN, extra={})
    assert out.index(_NO_TOKEN) < out.index("HOUSE RULES BLOCK")


def test_gates_are_independent(monkeypatch) -> None:
    """Every production agent sets shared_context: false and still needs language."""
    out = _compose(monkeypatch, instructions=_NO_TOKEN, extra={"shared_context": False})
    assert "HOUSE RULES BLOCK" not in out and "## Output language" in out

    out = _compose(monkeypatch, instructions=_NO_TOKEN, extra={"output_language": False})
    assert "HOUSE RULES BLOCK" in out and "## Output language" not in out


def test_opted_out_agent_with_token_fails_loud(monkeypatch) -> None:
    """Otherwise the literal token would be shipped to the model."""
    with pytest.raises(RuntimeError, match="OUTPUT_LANGUAGE"):
        _compose(monkeypatch, instructions=_WITH_TOKEN, extra={"output_language": False})


def test_empty_shared_dir_adds_no_separator(monkeypatch) -> None:
    out = _compose(monkeypatch, instructions=_NO_TOKEN, extra={}, shared="")
    assert "# System rules" not in out


def test_bare_instructions_when_nothing_trails(monkeypatch) -> None:
    """No "# Agent role" heading unless another block follows it.

    Every production agent sets shared_context: false, so wrapping
    unconditionally silently changed all ten prompts — it measured as ~30%
    longer tier-2 `impact` output on the holdout set.
    """
    out = _compose(
        monkeypatch,
        instructions=_NO_TOKEN,
        extra={"shared_context": False, "output_language": False},
    )
    assert out == _NO_TOKEN

    # A token-carrying prompt with nothing trailing is still bare.
    out = _compose(monkeypatch, instructions=_WITH_TOKEN, extra={"shared_context": False})
    assert not out.startswith("# Agent role")
    assert out.startswith("Write summary in Simplified Chinese.")


def test_heading_appears_once_something_trails(monkeypatch) -> None:
    out = _compose(monkeypatch, instructions=_NO_TOKEN, extra={})
    assert out.startswith("# Agent role")


def test_language_rule_alone_never_adds_the_heading(monkeypatch) -> None:
    """Turning the setting on must not silently reshape an unmigrated prompt.

    knowledge_classifier has no token and opts out of shared context; before
    this guard, setting SIGNAL_OUTPUT_LANG gave it a "# Agent role" heading it
    never had — the same heading that measured +31% tier-2 output.
    """
    off = _compose(monkeypatch, instructions=_NO_TOKEN,
                   extra={"shared_context": False}, lang=None)
    on = _compose(monkeypatch, instructions=_NO_TOKEN,
                  extra={"shared_context": False}, lang="zh")
    assert not off.startswith("# Agent role")
    assert not on.startswith("# Agent role")
    # Enabling the setting adds the rule and nothing else.
    assert on.startswith(_NO_TOKEN) and "## Output language" in on
