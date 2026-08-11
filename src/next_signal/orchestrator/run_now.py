"""Run one workflow's manual entry point by name.

Lives in the orchestrator rather than the CLI because it is composition, not
presentation: the CLI's ``run-workflow`` and the scheduler's job chain are both
callers. Imports stay inside the function so importing this module does not pull
agno into a CLI invocation that never runs a workflow.
"""

from __future__ import annotations


def run_workflow_now(workflow: str, inputs: dict | None = None) -> dict:
    """Resolve ``extra.run_now`` for ``workflow`` and call it."""
    from next_signal.core.config import load_workflow
    from next_signal.orchestrator.runnable_loader import load_factory

    try:
        cfg = load_workflow(workflow)
    except FileNotFoundError as e:
        raise RuntimeError(f"manual run is not implemented for workflow: {workflow}") from e
    run_now = str(cfg.extra.get("run_now") or "").strip()
    if not run_now:
        raise RuntimeError(f"manual run is not implemented for workflow: {workflow}")
    return load_factory(run_now)(**(inputs or {}))
