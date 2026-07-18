"""Expose configured workflows as agent-facing tools."""

from __future__ import annotations

from agno.tools import tool
from agno.tools.workflow import WorkflowTools

from paca.core.config import WorkflowConfig, list_workflows, load_workflow
from paca.orchestrator.runnable_loader import load_factory


def build_workflow_tools(cfg: WorkflowConfig, tool_name: str):
    """Build the agent-facing tool for one workflow.

    A workflow that names `extra.tool_fn` is exposed as that callable — it must
    return a JSON-safe value, because agno serializes a tool's result back to
    the model. Workflows without `tool_fn` fall back to agno's generic
    `WorkflowTools`, whose `run_workflow` does `json.dumps(result.to_dict())` on
    the raw workflow output and so cannot carry rich step objects.
    """
    tool_fn = cfg.extra.get("tool_fn")
    if tool_fn:
        return tool(name=tool_name)(load_factory(tool_fn))
    return WorkflowTools(
        workflow=load_factory(cfg.factory)(),
        enable_run_workflow=True,
        enable_think=False,
        enable_analyze=False,
    )


def register_workflow_tools(registry) -> None:
    """Register every workflow config that exposes a tool."""
    for name in list_workflows():
        cfg = load_workflow(name)
        if not cfg.enabled or not cfg.expose.tool.enabled:
            continue
        tool_name = cfg.expose.tool.name or f"{cfg.name}_workflow"
        registry.register(tool_name, build_workflow_tools(cfg, tool_name))
