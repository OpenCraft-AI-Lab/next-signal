"""Artifact edit phase: clean the body, then write frontmatter — two agent passes.

The old single pass made one agent emit the rewritten body and every frontmatter
field in one large JSON object; a local model would intermittently drop a field
(e.g. an empty `summary`). Splitting keeps each call's output small and focused:
`clean_body` runs `knowledge_artifact_editor` and takes plain markdown back;
`write_frontmatter` runs `knowledge_frontmatter` under the `FrontmatterDraft`
pydantic schema. A deterministic post-check still guards against a model
summarizing the body; failures raise so the step can retry.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from paca.agents.loader import build_from_name
from paca.agents.structured import run_structured
from paca.workflows.stages.knowledge_ingest.artifact import KnowledgeArtifact
from paca.workflows.stages.knowledge_ingest.schemas import FrontmatterDraft

logger = logging.getLogger(__name__)

_MAX_MARKDOWN_CHARS = 64000
_MIN_LONG_TEXT_RETENTION = 0.6
# Cleaning a whisper transcript legitimately drops filler, repeats, and outro
# copy — only a true summarization (well below this) should trip the guard.
_MIN_TRANSCRIPT_RETENTION = 0.70
# A GitHub README is supposed to be condensed aggressively (drop badges, install
# commands, sponsor blocks, etc.). The floor is only a safety net for
# collapse-to-one-line failure modes — heavy condensation is expected.
_MIN_GITHUB_README_RETENTION = 0.20


def clean_body(artifact: KnowledgeArtifact) -> KnowledgeArtifact:
    """Run knowledge_artifact_editor to clean and correct the body.

    For a transcript source the `# title` + `## Transcript` scaffold is kept
    verbatim and only the transcript prose is sent to the model — it cannot
    rewrite or invent headings it never sees. Articles are cleaned whole, with
    the retention and heading guards applied to the full body.
    """
    original = artifact.markdown
    if not original.strip():
        raise RuntimeError("artifact editor received empty markdown")
    if artifact.source_type in {"bilibili", "youtube"} and "## Transcript" in original:
        head, sep, prose = original.partition("## Transcript")
        cleaned = _run_editor(artifact, prose.strip())
        _check_summarized("transcript", prose, cleaned, _MIN_TRANSCRIPT_RETENTION)
        artifact.markdown = f"{head.rstrip()}\n\n{sep}\n\n{cleaned}\n"
    elif artifact.source_type == "github" and "## README" in original:
        # Mirror the transcript branch: the structured signal sections above
        # `## README` are kept verbatim (they were assembled deliberately), and
        # only the noisy README prose is condensed by the github-specific cleaner.
        head, sep, prose = original.partition("## README")
        cleaned = _run_editor(
            artifact, prose.strip(), agent_name="knowledge_github_cleaner"
        )
        _check_summarized(
            "github-readme", prose, cleaned, _MIN_GITHUB_README_RETENTION
        )
        artifact.markdown = f"{head.rstrip()}\n\n{sep}\n\n{cleaned}\n"
    else:
        cleaned = _run_editor(artifact, original.strip())
        _check_summarized("body", original, cleaned, _MIN_LONG_TEXT_RETENTION)
        if artifact.assets_dir is not None:
            _warn_dropped_image_refs(original, cleaned)
        artifact.markdown = cleaned
    return artifact


def _run_editor(
    artifact: KnowledgeArtifact,
    body: str,
    *,
    agent_name: str = "knowledge_artifact_editor",
) -> str:
    """Send a body to the named cleaner agent; return the cleaned plain markdown."""
    agent = build_from_name(agent_name)
    response = agent.run(
        json.dumps(
            {
                "source_type": artifact.source_type,
                "title": artifact.title or artifact.value,
                "markdown": body[:_MAX_MARKDOWN_CHARS],
            },
            ensure_ascii=False,
        )
    )
    cleaned = _strip_code_fence(str(getattr(response, "content", response))).strip()
    if not cleaned:
        raise RuntimeError("knowledge artifact editor returned an empty body")
    return cleaned


def write_frontmatter(artifact: KnowledgeArtifact) -> KnowledgeArtifact:
    """Run the frontmatter agent under FrontmatterDraft; set the fields."""
    if not artifact.markdown.strip():
        raise RuntimeError("frontmatter step received empty markdown")
    agent_name = (
        "knowledge_github_summary"
        if artifact.source_type == "github"
        else "knowledge_frontmatter"
    )
    agent = build_from_name(agent_name)
    agent_input = json.dumps(
        {
            "source_type": artifact.source_type,
            "category": artifact.category,
            "title": artifact.title or artifact.value,
            "metadata": _public_metadata(artifact.metadata),
            "markdown": artifact.markdown.strip()[:_MAX_MARKDOWN_CHARS],
        },
        ensure_ascii=False,
    )
    draft = run_structured(agent, agent_input, FrontmatterDraft)
    artifact.title = draft.title or artifact.title
    artifact.artifact_edit = draft.to_artifact_edit()
    return artifact


def _strip_code_fence(text: str) -> str:
    """Drop a single ```-fence wrapping the whole body, if the model added one."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.split("\n")[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _check_summarized(label: str, original: str, cleaned: str, min_retention: float) -> None:
    """Reject an edited body that lost too much content to be a clean, not a summary."""
    original_len = _content_length(original)
    cleaned_len = _content_length(cleaned)
    if original_len >= 2000 and cleaned_len < int(original_len * min_retention):
        raise RuntimeError(
            f"knowledge artifact editor appears to have summarized the {label} "
            f"({cleaned_len}/{original_len} content chars)"
        )


def _public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if not key.startswith("_") and key != "transcript_path"
    }


def _content_length(text: str) -> int:
    # UTF-8 byte length, not char count: lets the retention guard compare bodies
    # across languages. A faithful EN→ZH translation drops to ~33% chars but
    # stays at ~100% bytes (Chinese = 3 bytes/char, English ASCII = 1 byte/char).
    return len(re.sub(r"\s+", "", text).encode("utf-8"))


def _warn_dropped_image_refs(original: str, cleaned: str) -> None:
    """Log a warning for any local `images/...` references the editor dropped.

    Local image references reaching the editor came from opencli's downloaded
    image set; if they vanish in the cleaned body, surface that so the user
    can decide whether the loss matters. Not fatal — a few missing images
    rarely justifies retrying the whole clean.
    """
    dropped = _local_image_refs(original) - _local_image_refs(cleaned)
    if dropped:
        logger.warning(
            "knowledge artifact editor dropped %d local image reference(s): %s",
            len(dropped),
            sorted(dropped),
        )


def _local_image_refs(text: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(r"!\[[^\]]*\]\((images/[^)\s]+)\)", text)
    }
