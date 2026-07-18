from __future__ import annotations

import pytest
from pydantic import BaseModel

from paca.agents.structured import run_structured


class _Probe(BaseModel):
    value: int


class _Response:
    def __init__(self, content) -> None:
        self.content = content


class _SeqAgent:
    """Agent stub returning a fixed sequence of replies (the last one repeats)."""

    name = "probe"

    def __init__(self, replies: list) -> None:
        self._replies = replies
        self.calls = 0

    def run(self, message, **kwargs):
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return _Response(reply)


def test_run_structured_returns_validated_instance() -> None:
    agent = _SeqAgent(['{"value": 7}'])
    result = run_structured(agent, "input", _Probe)
    assert result.value == 7
    assert agent.calls == 1


def test_run_structured_repairs_after_bad_output() -> None:
    agent = _SeqAgent(['{"value": "not-an-int"}', '{"value": 9}'])
    result = run_structured(agent, "input", _Probe)
    assert result.value == 9
    assert agent.calls == 2  # initial call + one repair round


def test_run_structured_raises_when_never_valid() -> None:
    agent = _SeqAgent(['{"value": "bad"}'])
    with pytest.raises(RuntimeError, match="probe"):
        run_structured(agent, "input", _Probe)
    assert agent.calls == 2  # initial + one repair, then loud failure


def test_run_structured_accepts_already_parsed_instance() -> None:
    agent = _SeqAgent([_Probe(value=3)])
    result = run_structured(agent, "input", _Probe)
    assert result.value == 3


# ---------------------------------------------------------------------------
# Lenient JSON fallback — covers the xgrammar near-miss failure mode where the
# extracted text is structurally close to JSON but strict json.loads rejects it
# (trailing comma, unquoted key, etc.). json5 salvages these without a retry.
# ---------------------------------------------------------------------------


class _Doc(BaseModel):
    summary: str
    score: int


def test_run_structured_recovers_from_trailing_comma() -> None:
    """Real xgrammar near-miss: trailing comma before closing brace."""
    bad = '{"summary": "hi", "score": 7,}'
    agent = _SeqAgent([bad])
    result = run_structured(agent, "input", _Doc)
    assert result.summary == "hi" and result.score == 7
    assert agent.calls == 1  # no repair round needed


def test_run_structured_recovers_from_single_quotes() -> None:
    """Some Qwen outputs come back with single-quoted strings under load."""
    bad = "{'summary': 'hi', 'score': 7}"
    agent = _SeqAgent([bad])
    result = run_structured(agent, "input", _Doc)
    assert result.summary == "hi" and result.score == 7
    assert agent.calls == 1


def test_run_structured_still_repairs_when_lenient_also_fails() -> None:
    """If lenient parse also fails (bad type), we still get the repair round."""
    agent = _SeqAgent(['{"summary": "hi", "score": "not-an-int",}', '{"summary": "hi", "score": 9}'])
    result = run_structured(agent, "input", _Doc)
    assert result.score == 9
    assert agent.calls == 2
