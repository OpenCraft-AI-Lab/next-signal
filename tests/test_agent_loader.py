from __future__ import annotations

import pytest

from next_signal.agents import loader
from next_signal.core import language as language_module
from next_signal.core.config import AgentConfig, load_agent


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


def _compose(
    monkeypatch, *, instructions, extra, lang="zh", shared="HOUSE RULES BLOCK", override=None
):
    """Patch `global_language` at its source (next_signal.core.language) rather than
    the value `_compose_instructions` receives directly — this exercises the
    real `normalize_policy`/`resolve_language` dispatch, including `off`
    never touching `global_language` at all and `same_as_source` ignoring it
    entirely in favor of `override`."""
    monkeypatch.setattr(loader, "shared_context", lambda: shared)
    monkeypatch.setattr(language_module, "global_language", lambda: lang)
    return loader._compose_instructions(
        AgentConfig(
            name="probe",
            model_profile="local",
            instructions=instructions,
            markdown=False,
            add_history_to_context=False,
            extra=extra,
        ),
        override=override,
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


def test_global_policy_always_resolves_a_concrete_language(monkeypatch) -> None:
    """Unlike the retired env-var mechanism, the `global` policy has no
    'unset' state at the loader level — `global_language()` always returns a
    real value (preference file or the hardcoded default), never None."""
    out = _compose(monkeypatch, instructions=_WITH_TOKEN, extra={}, lang="en")
    assert "Write summary in English." in out
    assert "{{OUTPUT_LANGUAGE}}" not in out


def test_prompt_without_token_gets_appended_block(monkeypatch) -> None:
    """Unmigrated prompts still receive the rule rather than silently missing it."""
    out = _compose(monkeypatch, instructions=_NO_TOKEN, extra={"shared_context": False})
    assert "## Output language" in out
    assert out.index(_NO_TOKEN) < out.index("## Output language")


def test_off_policy_appends_nothing_without_token(monkeypatch) -> None:
    out = _compose(
        monkeypatch, instructions=_NO_TOKEN, extra={"output_language": "off"}
    )
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


def test_bare_boolean_false_still_means_off(monkeypatch) -> None:
    """Back-compat: the three agents shipped before the policy model existed
    still say `output_language: false` in YAML, and must behave identically."""
    out = _compose(monkeypatch, instructions=_NO_TOKEN, extra={"output_language": False})
    assert "## Output language" not in out


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
    unconditionally silently changed all ten prompts once — it measured as
    ~30% longer tier-2 `impact` output on the holdout set.
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
    the original output-language change, enabling the setting gave it a
    "# Agent role" heading it never had — the same heading that measured
    +31% tier-2 output.
    """
    off = _compose(
        monkeypatch,
        instructions=_NO_TOKEN,
        extra={"shared_context": False, "output_language": "off"},
    )
    on = _compose(monkeypatch, instructions=_NO_TOKEN,
                  extra={"shared_context": False}, lang="zh")
    assert not off.startswith("# Agent role")
    assert not on.startswith("# Agent role")
    # Enabling the setting adds the rule and nothing else.
    assert on.startswith(_NO_TOKEN) and "## Output language" in on


# ---------------------------------------------------------------------------
# same_as_source policy: caller-supplied override
# ---------------------------------------------------------------------------


def test_same_as_source_uses_the_override(monkeypatch) -> None:
    out = _compose(
        monkeypatch,
        instructions=_WITH_TOKEN,
        extra={"shared_context": False, "output_language": "same_as_source"},
        override="en",
    )
    assert "Write summary in English." in out


def test_same_as_source_ignores_the_global_preference(monkeypatch) -> None:
    """The whole point of this policy: it must not fall back to `global`."""
    out = _compose(
        monkeypatch,
        instructions=_WITH_TOKEN,
        extra={"shared_context": False, "output_language": "same_as_source"},
        lang="en",  # global_language() patched to "en"...
        override="zh",  # ...but the override must win.
    )
    assert "Write summary in Simplified Chinese." in out


def test_same_as_source_without_override_raises(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="same_as_source"):
        _compose(
            monkeypatch,
            instructions=_WITH_TOKEN,
            extra={"shared_context": False, "output_language": "same_as_source"},
        )


def test_fixed_policy_ignores_global_and_override(monkeypatch) -> None:
    out = _compose(
        monkeypatch,
        instructions=_WITH_TOKEN,
        extra={"shared_context": False, "output_language": "fixed:en"},
        lang="zh",
        override="zh",
    )
    assert "Write summary in English." in out


# ---------------------------------------------------------------------------
# The shipped ingest split: index entries follow the setting, bodies don't
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent_name", "expected_rule"),
    [
        # `same_as_source` -> the override. Appended-block delivery (no token).
        ("knowledge_artifact_editor", "prose field of your output in Simplified Chinese"),
        ("knowledge_github_cleaner", "prose field of your output in Simplified Chinese"),
        # `global` -> the preference. Token substituted in the prompt's own line.
        ("knowledge_frontmatter", "Write `title` and `summary` in English"),
        ("knowledge_github_summary", "Write `summary` in English"),
    ],
)
def test_ingest_agents_split_between_source_and_setting(
    monkeypatch, agent_name, expected_rule
) -> None:
    """One Chinese item under an English content-language setting.

    The body cleaners must target the source (`zh`, from the override) so the
    wiki keeps its only copy of the source text; the frontmatter agents must
    target the setting (`en`) because their output is the reader's index entry.
    Loads the shipped YAML, so flipping either policy by accident fails here.
    """
    monkeypatch.setattr(language_module, "global_language", lambda: "en")
    out = loader._compose_instructions(load_agent(agent_name), override="zh")
    assert expected_rule in out
