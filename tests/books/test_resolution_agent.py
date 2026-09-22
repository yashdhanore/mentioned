from __future__ import annotations

from types import SimpleNamespace

import httpx
from google.genai import errors as genai_errors
from google.genai import types

from src.books.resolution import Resolution, score_candidate
from src.books.resolution_agent import SEARCH_TOOL, SUBMIT_TOOL, resolve_with_agent
from src.books.schemas import GoogleBook
from src.extraction.google_books import BooksSearchResult

REJECTED = GoogleBook(
    provider_volume_id="rejected-1", title="Toni Morrison", authors=["Toni Morrison"]
)
FOUND = GoogleBook(provider_volume_id="found-1", title="The Bluest Eye", authors=["Toni Morrison"])


def _prior() -> Resolution:
    candidate = score_candidate(REJECTED, "The Bluest Eye", "Toni Morrison")
    return Resolution(
        status="ambiguous",
        candidates=(candidate,),
        queries=("intitle:The Bluest Eye+inauthor:Toni Morrison",),
        searches=1,
    )


def _call(name: str, call_id: str | None = None, **args) -> types.FunctionCall:
    return types.FunctionCall(id=call_id, name=name, args=args)


def _response(*calls: types.FunctionCall) -> SimpleNamespace:
    content = types.Content(role="model", parts=[types.Part(function_call=call) for call in calls])
    return SimpleNamespace(
        function_calls=list(calls),
        candidates=[SimpleNamespace(content=content)],
        usage_metadata=SimpleNamespace(
            prompt_token_count=100, candidates_token_count=10, thoughts_token_count=None
        ),
    )


class FakeClient:
    def __init__(self, *responses):
        self.configs: list[types.GenerateContentConfig] = []
        self.requests: list[list[types.Content]] = []
        self._responses = list(responses)
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.configs.append(config)
        self.requests.append(list(contents))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _search(result: BooksSearchResult):
    queries: list[str] = []

    def search(query: str) -> BooksSearchResult:
        queries.append(query)
        return result

    search.queries = queries
    return search


def _allowed(config: types.GenerateContentConfig) -> list[str]:
    return config.tool_config.function_calling_config.allowed_function_names


def test_resolves_a_volume_found_by_its_own_search():
    client = FakeClient(
        _response(_call(SEARCH_TOOL, query='intitle:"The Bluest Eye"')),
        _response(_call(SUBMIT_TOOL, volume_id="found-1", reason="standalone novel")),
    )
    search = _search(BooksSearchResult(status="found", books=[FOUND]))
    usage: dict[str, int] = {}

    result = resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=search,
        client=client,
        model="test-model",
        usage=usage,
    )

    assert result.status == "resolved"
    assert result.book is FOUND
    assert result.method == "agent"
    assert result.reason == "standalone novel"
    assert result.searches == 2
    assert search.queries == ['intitle:"The Bluest Eye"']
    assert usage == {"calls": 2, "input_tokens": 200, "output_tokens": 20}


def test_refuses_a_volume_it_never_saw():
    client = FakeClient(_response(_call(SUBMIT_TOOL, volume_id="made-up", reason="guess")))

    result = resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=_search(BooksSearchResult(status="not_found")),
        client=client,
        model="test-model",
    )

    assert result.status == "ambiguous"
    assert result.book is None
    assert "never saw" in result.reason


def test_can_pick_a_candidate_the_check_rejected():
    client = FakeClient(_response(_call(SUBMIT_TOOL, volume_id="rejected-1", reason="same")))

    result = resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=_search(BooksSearchResult(status="not_found")),
        client=client,
        model="test-model",
    )

    assert result.status == "resolved"
    assert result.book is REJECTED


def test_giving_up_keeps_the_prior_status():
    client = FakeClient(_response(_call(SUBMIT_TOOL, volume_id="", reason="not in catalog")))

    result = resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=_search(BooksSearchResult(status="not_found")),
        client=client,
        model="test-model",
    )

    assert result.status == "ambiguous"
    assert result.method == "agent"
    assert result.reason == "not in catalog"


def test_only_submit_is_allowed_after_the_search_budget():
    client = FakeClient(
        _response(_call(SEARCH_TOOL, query="one")),
        _response(_call(SEARCH_TOOL, query="two")),
        _response(_call(SUBMIT_TOOL, volume_id="", reason="none")),
    )

    resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=_search(BooksSearchResult(status="not_found")),
        client=client,
        model="test-model",
        max_searches=2,
    )

    assert [_allowed(config) for config in client.configs] == [
        [SEARCH_TOOL, SUBMIT_TOOL],
        [SEARCH_TOOL, SUBMIT_TOOL],
        [SUBMIT_TOOL],
    ]


def test_fails_open_when_the_model_call_fails():
    prior = _prior()
    client = FakeClient(genai_errors.APIError(503, {"error": {"message": "unavailable"}}))

    result = resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        prior,
        search=_search(BooksSearchResult(status="not_found")),
        client=client,
        model="test-model",
    )

    assert result is prior


def _function_responses(content: types.Content) -> list[types.FunctionResponse]:
    return [part.function_response for part in content.parts]


def test_answers_every_call_in_a_turn_even_past_the_search_budget():
    client = FakeClient(
        _response(
            _call(SEARCH_TOOL, call_id="c1", query="first"),
            _call(SEARCH_TOOL, call_id="c2", query="second"),
        ),
        _response(_call(SUBMIT_TOOL, volume_id="found-1", reason="found")),
    )
    search = _search(BooksSearchResult(status="found", books=[FOUND]))

    result = resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=search,
        client=client,
        model="test-model",
        max_searches=1,
    )

    assert result.book is FOUND
    assert search.queries == ["first"]
    [answered, over_budget] = _function_responses(client.requests[1][-1])
    assert (answered.id, answered.response["status"]) == ("c1", "found")
    assert over_budget.id == "c2"
    assert "budget" in over_budget.response["error"]


def test_a_failing_catalog_search_is_reported_to_the_model():
    def failing_search(_query: str) -> BooksSearchResult:
        raise RuntimeError("catalog down")

    client = FakeClient(
        _response(_call(SEARCH_TOOL, call_id="c1", query="anything")),
        _response(_call(SUBMIT_TOOL, volume_id="", reason="catalog unavailable")),
    )

    result = resolve_with_agent(
        "The Bluest Eye",
        "Toni Morrison",
        _prior(),
        search=failing_search,
        client=client,
        model="test-model",
    )

    assert result.status == "ambiguous"
    [answer] = _function_responses(client.requests[1][-1])
    assert answer.response == {"error": "catalog search failed"}


def test_fails_open_on_timeouts_and_unreadable_responses():
    for error in (
        httpx.ReadTimeout("timed out"),
        genai_errors.UnknownApiResponseError("not json"),
    ):
        prior = _prior()
        result = resolve_with_agent(
            "The Bluest Eye",
            "Toni Morrison",
            prior,
            search=_search(BooksSearchResult(status="not_found")),
            client=FakeClient(error),
            model="test-model",
        )
        assert result is prior
