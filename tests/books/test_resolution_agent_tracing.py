"""The resolution agent's trace, checked in isolation because the agent runs only in the eval.

Ways it can fail (T13 in the tracing implementation notes), written before the tracing code:
- The agent is one opaque span, so what it saw and decided after each search is lost.
- Tool calls nest inside the generation that asked for them instead of beside it, or dangle
  at the trace root.
- A turn's generation lacks its model, its conversation so far, or its token usage.
- A model call that fails is not marked, so an agent that silently gave up looks like success.
- A refused pick (a volume the agent never saw) looks like an accepted one.
"""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.books.resolution_agent import SEARCH_TOOL, SUBMIT_TOOL, resolve_with_agent
from src.config import LangfuseConfig, Settings
from src.extraction.google_books import BooksSearchResult
from src.observability import configure_tracing, flush_tracing, shutdown_tracing
from tests.books.test_resolution_agent import FOUND, FakeClient, _call, _prior, _response, _search


@pytest.fixture
def spans(monkeypatch):
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    exporter = InMemorySpanExporter()
    # A fresh public key per test: the SDK keeps one client per key for the life of the
    # process, and the previous test's client is shut down.
    settings = Settings(
        langfuse=LangfuseConfig(
            public_key=f"pk-lf-agent-{uuid4().hex}",
            secret_key="sk-lf-agent-test",
            base_url="http://127.0.0.1:9",
        )
    )
    configure_tracing(settings, span_exporter=exporter)

    def finished():
        flush_tracing()
        return {span.name: span for span in exporter.get_finished_spans()}, list(
            exporter.get_finished_spans()
        )

    yield finished
    shutdown_tracing()


def _attr(span, key):
    value = span.attributes.get(key)
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def test_each_turn_is_a_generation_with_its_tool_calls_beside_it(spans):
    client = FakeClient(
        _response(_call(SEARCH_TOOL, "call-1", query='intitle:"The Bluest Eye"')),
        _response(_call(SUBMIT_TOOL, "call-2", volume_id="found-1", reason="standalone novel")),
    )

    result = resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=_search(BooksSearchResult(status="found", books=[FOUND])),
        client=client,
        model="gemini-3.1-flash-lite",
    )
    by_name, all_spans = spans()

    assert result.status == "resolved"
    agent = by_name["resolve-book-agent"]
    assert _attr(agent, "langfuse.observation.type") == "agent"
    assert _attr(agent, "langfuse.observation.output")["book"]["volume_id"] == "found-1"

    turns = [span for span in all_spans if span.name == "choose-book-action"]
    tools = [span for span in all_spans if span.name in ("search-books", "submit-resolution")]
    assert len(turns) == 2
    assert [span.name for span in tools] == ["search-books", "submit-resolution"]
    for span in [*turns, *tools]:
        assert span.parent.span_id == agent.context.span_id

    first, second = turns
    assert _attr(first, "langfuse.observation.type") == "generation"
    assert _attr(first, "langfuse.observation.model.name") == "gemini-3.1-flash-lite"
    assert _attr(first, "langfuse.observation.usage_details") == {
        "input": 100,
        "input_audio": 0,
        "output": 10,
        "output_reasoning": 0,
    }
    assert _attr(first, "langfuse.observation.cost_details")["total"] > 0
    # The second turn saw the first search's result as a tool message.
    messages = _attr(second, "langfuse.observation.input")
    assert [message["role"] for message in messages] == ["user", "assistant", "tool"]
    assert messages[1]["tool_calls"][0]["function"]["name"] == SEARCH_TOOL
    assert json.loads(messages[2]["content"])["volumes"][0]["volume_id"] == "found-1"
    assert _attr(tools[0], "langfuse.observation.output")["status"] == "found"


def test_a_failed_model_call_marks_the_turn_and_the_agent(spans):
    client = FakeClient(httpx.ReadTimeout("slow"))

    result = resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=_search(BooksSearchResult(status="not_found")),
        client=client,
        model="gemini-3.1-flash-lite",
    )
    by_name, _ = spans()

    assert result.status == "ambiguous"
    turn = by_name["choose-book-action"]
    assert _attr(turn, "langfuse.observation.level") == "ERROR"
    assert _attr(turn, "langfuse.observation.status_message") == "ReadTimeout"
    agent = by_name["resolve-book-agent"]
    assert _attr(agent, "langfuse.observation.level") == "WARNING"


def test_a_refused_pick_is_visible_on_the_submit_call(spans):
    client = FakeClient(_response(_call(SUBMIT_TOOL, "call-1", volume_id="made-up", reason="x")))

    resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=_search(BooksSearchResult(status="not_found")),
        client=client,
        model="gemini-3.1-flash-lite",
    )
    by_name, _ = spans()

    submit = _attr(by_name["submit-resolution"], "langfuse.observation.output")
    assert submit["status"] == "ambiguous"
    assert "never saw" in submit["reason"]
