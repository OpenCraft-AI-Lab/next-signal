"""Thin workflow shell for the info-radar collector.

This module exists only so a manual run (keyed off the workflow name) can
invoke the collector. It contains no LLM logic, no agno ``Workflow`` machinery,
and is never exposed to AgentOS — the YAML sets ``expose.agent_os: false`` and
``extra.run_now`` to ``:run`` below, which is all that
``paca run-workflow info_radar_pull`` calls. Day-to-day pulls run through the
dedicated ``paca info-radar pull`` command instead.
"""

from __future__ import annotations

from typing import Any, NoReturn


def run(**inputs: Any) -> dict[str, Any]:
    """Pull every enabled source and return a run summary."""
    from paca.collectors.info_radar.runner import all_failed, run_all

    results = run_all()
    summary = {
        "sources_run": len(results),
        "items_written": sum(r.written for r in results),
        "items_skipped": sum(r.skipped for r in results),
        "errors": [
            {"source": r.name, "error": r.error} for r in results if r.error is not None
        ],
        "all_failed": all_failed(results),
    }
    return summary


def factory() -> NoReturn:
    """Placeholder so ``WorkflowConfig.factory`` is satisfied; raises if called.

    The YAML sets ``expose.agent_os: false`` so AgentOS never invokes this.
    A misconfiguration that flips it on will fail loudly instead of silently
    producing a broken handle.
    """
    raise NotImplementedError(
        "info_radar_pull is not an AgentOS workflow; it is invoked via "
        "extra.run_now (`paca run-workflow info_radar_pull`)."
    )
