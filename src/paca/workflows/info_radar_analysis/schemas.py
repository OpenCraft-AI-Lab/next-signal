"""Pydantic schemas for the three info-radar-analysis agents.

Each schema is passed to ``paca.agents.structured.run_structured`` as the
per-call ``output_schema``. OMLX's xgrammar constrained decoding then forces
the model to emit JSON that matches.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Tier1Verdict(BaseModel):
    """Cheap title+description filter against the user's goals.

    The agent never sees this type directly — it produces ``Tier1Batch`` (a
    list of ``Tier1Decision``). The runner unpacks per-item verdicts into
    ``Tier1Verdict`` for the downstream pipeline because the per-item path
    (drop → persist → mark_seen, keep → fetch → tier2) doesn't care about
    batch indices.
    """

    verdict: Literal["keep", "drop"]
    reason: str = Field(..., description="One short sentence explaining the verdict.")


class Tier1Decision(BaseModel):
    """One per-item entry inside a Tier1Batch.

    ``index`` mirrors the position of the corresponding item in the input
    array so a model that re-orders or drops an entry can be detected and
    rejected by the runner.
    """

    index: int = Field(..., ge=0, description="Position in the input items[] array.")
    verdict: Literal["keep", "drop"]
    reason: str = Field(..., description="One short sentence explaining the verdict.")


class Tier1Batch(BaseModel):
    """Agent output schema for the batched tier-1 filter.

    The agent receives N items and MUST return N decisions covering exactly
    the indices ``0..N-1``. The runner validates this; on any mismatch
    (wrong count, wrong indices, schema invalid) the runner falls back to
    per-item single calls.
    """

    decisions: list[Tier1Decision]


class Tier2Analysis(BaseModel):
    """Goal-grounded impact analysis on a single kept item."""

    summary: str = Field(
        ...,
        description="2-4 sentence factual summary of the item's actual content.",
    )
    impact: str = Field(
        ...,
        description="Markdown describing the item's impact on the user's declared goals "
        "specifically — what changes for them, why it matters.",
    )
    score: int = Field(
        ...,
        ge=0,
        le=100,
        description="0=zero relevance to any goal, 100=must-read for the user.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Short tags that classify the item (e.g. 'release', 'paper', 'incident').",
    )


class DedupVerdict(BaseModel):
    """Whether a new item is a paraphrase of a previously-pushed topic."""

    is_duplicate: bool
    matched_topic_id: int | None = Field(
        default=None,
        description="ID of the matched topic when is_duplicate=true; null otherwise.",
    )
    reason: str = Field(..., description="One short sentence explaining the decision.")
