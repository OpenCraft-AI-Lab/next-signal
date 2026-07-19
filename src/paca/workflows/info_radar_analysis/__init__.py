"""Two-tier LLM analysis of unseen radar_items.

Pipeline (per item, sequential — no agno Team):

    tier1_filter (title + description)
        ├─ verdict='drop' → mark seen, persist analysis row, done
        └─ verdict='keep' → fetch full content via folocli entry get
                            (with opportunistic YouTube subtitle enrichment)
                          → tier2_impact (summary + impact + score)
                          → dedup_gate (pgvector ANN + LLM judge)
                          → persist + mark seen

Every per-item failure is isolated: one bad item never aborts the batch.

This module is not an AgentOS workflow — it's invoked by the CLI via
``extra.run_now`` (see configs/workflows/info_radar_analysis.yaml).
"""

from __future__ import annotations

from typing import Any

__all__ = ["run", "factory"]


def run(**inputs: Any) -> dict:
    """Run the analysis batch. Lazy import so the package is importable
    before all its modules exist (during early implementation / testing).
    """
    from paca.workflows.info_radar_analysis.runner import run as _run

    return _run(**inputs)


def factory():
    """Placeholder so WorkflowConfig.factory parses; never called.

    The YAML sets ``expose.agent_os: false`` so AgentOS never tries to bind
    this. A misconfiguration that flips it on must fail loudly here rather
    than silently producing a broken handle.
    """
    raise NotImplementedError(
        "info_radar_analysis is not an AgentOS workflow; it is invoked via "
        "extra.run_now (`paca info-radar analyze` or `paca run-workflow`)."
    )
