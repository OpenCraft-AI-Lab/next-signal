from __future__ import annotations

import json

import pytest

import paca.workflows.stages.knowledge_ingest.artifact_editor as artifact_editor_mod
from paca.workflows.stages.knowledge_ingest import KnowledgeArtifact
from paca.workflows.stages.knowledge_ingest.artifact_editor import clean_body, write_frontmatter


def _artifact(
    *, source_type: str = "web", markdown: str = "# Body\n\nparagraph text."
) -> KnowledgeArtifact:
    return KnowledgeArtifact(
        value="https://example.com/x",
        source_type=source_type,
        digest="abc123",
        created_at="2026-05-15T00:00:00+00:00",
        category="knowledge",
        title="orig title",
        markdown=markdown,
        metadata={},
    )


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


def _stub_agent(monkeypatch, payload) -> None:
    """Replace build_from_name with an agent that returns a canned response.

    `payload` is plain markdown for the body cleaner, or a dict for the
    frontmatter writer.
    """
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)

    class FakeAgent:
        def run(self, agent_input, **kwargs):
            return _FakeResponse(text)

    monkeypatch.setattr(artifact_editor_mod, "build_from_name", lambda name: FakeAgent())


# --- clean_body -----------------------------------------------------------


def test_clean_body_sets_cleaned_markdown(monkeypatch) -> None:
    _stub_agent(monkeypatch, "# Body\n\ncleaned paragraph.")
    result = clean_body(_artifact())
    assert result.markdown == "# Body\n\ncleaned paragraph."


def test_clean_body_strips_code_fence(monkeypatch) -> None:
    _stub_agent(monkeypatch, "```markdown\n# Body\n\ncleaned.\n```")
    result = clean_body(_artifact())
    assert result.markdown == "# Body\n\ncleaned."


def test_clean_body_raises_on_empty_input(monkeypatch) -> None:
    _stub_agent(monkeypatch, "anything")
    with pytest.raises(RuntimeError, match="empty markdown"):
        clean_body(_artifact(markdown="   "))


def test_clean_body_raises_on_empty_output(monkeypatch) -> None:
    _stub_agent(monkeypatch, "   ")
    with pytest.raises(RuntimeError, match="empty body"):
        clean_body(_artifact())


def test_clean_body_rejects_summarized_body(monkeypatch) -> None:
    _stub_agent(monkeypatch, "字" * 100)
    with pytest.raises(RuntimeError, match="summarized the body"):
        clean_body(_artifact(markdown="字" * 2100))


def test_clean_body_keeps_transcript_scaffold(monkeypatch) -> None:
    """A transcript keeps its `# title` + `## Transcript` scaffold verbatim; only the
    prose is sent to the model, so it cannot rewrite or invent headings."""
    seen: list[str] = []

    class FakeAgent:
        def run(self, agent_input, **kwargs):
            seen.append(json.loads(agent_input)["markdown"])
            return _FakeResponse("cleaned spoken body.")

    monkeypatch.setattr(artifact_editor_mod, "build_from_name", lambda name: FakeAgent())

    result = clean_body(
        _artifact(source_type="bilibili", markdown="# Vid\n\n## Transcript\n\nspoken body.")
    )

    assert seen == ["spoken body."]
    assert result.markdown == "# Vid\n\n## Transcript\n\ncleaned spoken body.\n"


def test_clean_body_github_routes_to_github_cleaner(monkeypatch) -> None:
    """A github artifact sends only the README prose to `knowledge_github_cleaner`
    and keeps the structured signal sections above `## README` verbatim."""
    seen: list[tuple[str, str]] = []

    class FakeAgent:
        def __init__(self, name: str) -> None:
            self.name = name

        def run(self, agent_input, **kwargs):
            seen.append((self.name, json.loads(agent_input)["markdown"]))
            return _FakeResponse("Tight condensed README.")

    monkeypatch.setattr(
        artifact_editor_mod, "build_from_name", lambda name: FakeAgent(name)
    )

    body = (
        "# owner/repo\n\n## Repo Signals\n\n- Stars: 1234\n\n"
        "## Project Layout\n\n- src/\n\n## README\n\n"
        "[![CI](badge.svg)](https://ci) install with `pip install foo`. Real content here."
    )
    result = clean_body(_artifact(source_type="github", markdown=body))

    assert len(seen) == 1
    agent_name, sent = seen[0]
    assert agent_name == "knowledge_github_cleaner"
    assert sent.startswith("[![CI]")
    assert "Repo Signals" not in sent  # head was not sent to the cleaner
    assert "# owner/repo" in result.markdown
    assert "## Repo Signals" in result.markdown
    assert "- Stars: 1234" in result.markdown
    assert "Tight condensed README." in result.markdown
    # The README marker is preserved verbatim
    assert "## README" in result.markdown


def test_clean_body_non_github_uses_default_cleaner(monkeypatch) -> None:
    """Non-github artifacts stay on `knowledge_artifact_editor`, unchanged."""
    seen: list[str] = []

    class FakeAgent:
        def __init__(self, name: str) -> None:
            self.name = name

        def run(self, agent_input, **kwargs):
            seen.append(self.name)
            return _FakeResponse(json.loads(agent_input)["markdown"])

    monkeypatch.setattr(
        artifact_editor_mod, "build_from_name", lambda name: FakeAgent(name)
    )

    clean_body(_artifact(source_type="web", markdown="# Hello\n\nA body."))
    assert seen == ["knowledge_artifact_editor"]


def test_clean_body_github_collapse_below_floor_raises(monkeypatch) -> None:
    """If the github cleaner returns much less than 20% of the README's content
    chars, the retention guard raises (only triggers when the README is >= 2000)."""

    class FakeAgent:
        def __init__(self, name: str) -> None:
            self.name = name

        def run(self, agent_input, **kwargs):
            return _FakeResponse("x")  # single char — way below 20% floor

    monkeypatch.setattr(
        artifact_editor_mod, "build_from_name", lambda name: FakeAgent(name)
    )

    long_readme = "a" * 3000
    body = f"# owner/repo\n\n## Repo Signals\n\n- Stars: 1\n\n## README\n\n{long_readme}"
    with pytest.raises(RuntimeError, match="summarized the github-readme"):
        clean_body(_artifact(source_type="github", markdown=body))


# --- write_frontmatter ----------------------------------------------------


def test_write_frontmatter_populates_title_and_artifact_edit(monkeypatch) -> None:
    _stub_agent(
        monkeypatch,
        {
            "title": "Clean Title",
            "summary": "a dense factual summary.",
            "tags": ["alpha", "beta"],
            "freshness": "stable",
        },
    )
    result = write_frontmatter(_artifact())

    assert result.title == "Clean Title"
    assert result.artifact_edit == {
        "summary": "a dense factual summary.",
        "tags": ["alpha", "beta"],
        "freshness": "stable",
    }


def test_write_frontmatter_raises_on_empty_summary(monkeypatch) -> None:
    _stub_agent(monkeypatch, {"summary": "", "tags": ["a"]})
    with pytest.raises(RuntimeError, match="summary"):
        write_frontmatter(_artifact())


def test_write_frontmatter_raises_on_missing_tags(monkeypatch) -> None:
    _stub_agent(monkeypatch, {"summary": "s", "tags": []})
    with pytest.raises(RuntimeError, match="tag"):
        write_frontmatter(_artifact())


def test_write_frontmatter_github_routes_to_github_summary(monkeypatch) -> None:
    """A github artifact picks the github summary agent; non-github picks the default."""
    seen: list[str] = []

    class FakeAgent:
        def __init__(self, name: str) -> None:
            self.name = name

        def run(self, agent_input, **kwargs):
            seen.append(self.name)
            return _FakeResponse(
                json.dumps(
                    {
                        "title": "owner/repo",
                        "summary": "Does X. Value Y. Maturity active-development. Ecosystem python/cli.",
                        "tags": ["python", "cli"],
                        "freshness": "evolving",
                    },
                    ensure_ascii=False,
                )
            )

    monkeypatch.setattr(
        artifact_editor_mod, "build_from_name", lambda name: FakeAgent(name)
    )

    write_frontmatter(_artifact(source_type="github", markdown="# owner/repo\n\nbody"))
    write_frontmatter(_artifact(source_type="web", markdown="# Title\n\nbody"))

    assert seen == ["knowledge_github_summary", "knowledge_frontmatter"]
