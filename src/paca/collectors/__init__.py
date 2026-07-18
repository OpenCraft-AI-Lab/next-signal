"""Background data collectors.

Collectors are periodic, CLI-driven, non-LLM data movement: they invoke external
commands, parse stdout, and persist results to a business table. They are not
agent-facing (no ``tools/`` registration) and do not embed agno workflows.

The scheduler still dispatches by workflow name, so each collector gets a thin
``workflows/<name>.py`` shell whose only job is to call into the collector.
"""
