"""Run an agent and return its output validated against a pydantic schema.

agno's own structured-output parsing fails silently — it logs a warning and
leaves the raw string on the response. `run_structured` instead validates
loudly and, on a validation failure, re-prompts the agent with the exact error
and retries — the self-healing loop agno does not provide.

When strict ``json.loads`` rejects the extracted text we fall back to
``json5``, which tolerates the common LLM/xgrammar malformations (trailing
commas, unescaped quotes inside long Chinese strings, comments). This catches
the stochastic xgrammar failures we observed on tier-2 analyses without
giving the model another (likely identical) retry.
"""

from __future__ import annotations

import json5
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from paca.tools._json_extract import extract_json_object

T = TypeVar("T", bound=BaseModel)


def run_structured(agent, agent_input: str, schema: type[T], *, max_repairs: int = 1) -> T:
    """Run `agent`, return its output validated as `schema`.

    The schema is passed as agno's per-call `output_schema`, so a structured-
    output-capable model constrains its tokens to it. On a JSON or validation
    failure the agent is re-prompted with the exact error and retried up to
    `max_repairs` times; a still-invalid result raises `RuntimeError`.
    """
    message = agent_input
    last_error = ""
    for _ in range(max_repairs + 1):
        response = agent.run(message, output_schema=schema)
        content = getattr(response, "content", response)
        if isinstance(content, schema):
            return content
        raw = str(content)
        extracted = extract_json_object(raw)
        try:
            return schema.model_validate_json(extracted)
        except (ValidationError, ValueError) as strict_err:
            last_error = str(strict_err)
            # Tolerant fallback for the xgrammar near-misses (trailing commas,
            # unescaped quotes in Chinese strings, etc.). Same retry budget —
            # if this succeeds we skip the repair-prompt round-trip entirely.
            try:
                obj = json5.loads(extracted)
                return schema.model_validate(obj)
            except (ValidationError, ValueError) as lenient_err:
                last_error = f"strict: {strict_err}; lenient: {lenient_err}"
            message = _repair_prompt(agent_input, raw, last_error)
    name = getattr(agent, "name", None) or "agent"
    raise RuntimeError(f"{name} could not produce a valid {schema.__name__}: {last_error}")


def _repair_prompt(original: str, bad_output: str, error: str) -> str:
    return (
        f"{original}\n\n"
        "Your previous reply was rejected by schema validation.\n"
        f"Previous reply:\n{bad_output[:1500]}\n\n"
        f"Validation error:\n{error}\n\n"
        "Return ONLY corrected JSON that satisfies the schema."
    )
