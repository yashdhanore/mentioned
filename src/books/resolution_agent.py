"""A small tool-using agent for the book mentions the catalog check could not confirm.

`resolve_book` only knows the title the video model wrote down. When that is a
translated title, a series name, or a misspelling, every candidate fails the check.
This agent sees the rejected candidates, may search the catalog again with better
queries, and must pick a volume it has actually seen or give up. It is text-only:
the video is never sent again, so a call costs a few hundred tokens.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from src.books.resolution import BookSearch, Resolution, ScoredCandidate
from src.books.schemas import GoogleBook

logger = logging.getLogger(__name__)

MAX_AGENT_SEARCHES = 3
SEARCH_TOOL = "search_books"
SUBMIT_TOOL = "submit_resolution"
# The SDK raises APIError for HTTP errors, UnknownApiResponseError for unreadable
# responses, and lets httpx timeouts and connection errors through unwrapped.
MODEL_CALL_ERRORS = (genai_errors.APIError, genai_errors.UnknownApiResponseError, httpx.HTTPError)

AGENT_PROMPT = """\
A social video mentioned a book, and an automatic check could not match it to a catalog entry.
Find the catalog entry for this exact work, or conclude that it is not in the catalog.

Mentioned title: {title}
Mentioned author: {author}

Catalog results already rejected by the automatic title and author check:
{candidates}

The mention may use a translated title, the original-language title, a series name, a
shortened title, or a misspelled author. You may call {search} up to {max_searches} times with
Google Books query syntax, such as intitle:, inauthor:, or plain words.
Then call {submit} with the volume_id of an edition of this exact work.
Prefer a standalone edition over a collection that contains it.
Never choose a summary, a study guide, an analysis, or a different book by the same author.
If no result you have seen is this work, call {submit} with an empty volume_id.
"""

FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name=SEARCH_TOOL,
        description="Search the Google Books catalog. Returns up to 5 volumes.",
        parameters_json_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    ),
    types.FunctionDeclaration(
        name=SUBMIT_TOOL,
        description=(
            "Finish. Pass the volume_id of the matching catalog entry, "
            "or an empty volume_id if none of the results is this work."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "volume_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["volume_id", "reason"],
        },
    ),
]


def _volume_view(book: GoogleBook) -> dict[str, Any]:
    return {
        "volume_id": book.provider_volume_id,
        "title": book.title,
        "subtitle": book.subtitle,
        "authors": book.authors,
        "published_date": book.published_date,
        "print_type": book.print_type,
    }


def _candidate_lines(candidates: tuple[ScoredCandidate, ...]) -> str:
    if not candidates:
        return "(the catalog returned nothing)"
    return "\n".join(
        json.dumps({**_volume_view(c.book), "rejected_because": c.rejected_because})
        for c in candidates
    )


def _config(*, allow_search: bool) -> types.GenerateContentConfig:
    allowed = [SEARCH_TOOL, SUBMIT_TOOL] if allow_search else [SUBMIT_TOOL]
    return types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=FUNCTION_DECLARATIONS)],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.ANY,
                allowed_function_names=allowed,
            )
        ),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.0,
    )


def resolve_with_agent(
    title: str,
    author: str | None,
    prior: Resolution,
    *,
    search: BookSearch,
    client: genai.Client,
    model: str,
    max_searches: int = MAX_AGENT_SEARCHES,
    usage: dict[str, int] | None = None,
) -> Resolution:
    """Try to resolve a mention the catalog check left `ambiguous` or `not_found`.

    Fails open: any model or tool failure returns `prior` unchanged, and a pick the
    agent never saw in a search result is refused rather than trusted. Token counts
    are added to `usage` when given, so callers can price the agent."""
    seen: dict[str, GoogleBook] = {c.book.provider_volume_id: c.book for c in prior.candidates}
    prompt = AGENT_PROMPT.format(
        title=title,
        author=author or "unknown",
        candidates=_candidate_lines(prior.candidates),
        search=SEARCH_TOOL,
        submit=SUBMIT_TOOL,
        max_searches=max_searches,
    )
    contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    queries = list(prior.queries)
    searches = 0

    for _turn in range(max_searches + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=_config(allow_search=searches < max_searches),
            )
        except MODEL_CALL_ERRORS as exc:
            logger.warning("Book resolution agent call failed: %s: %s", type(exc).__name__, exc)
            return prior
        _record_usage(usage, response)
        calls = response.function_calls or []
        if not calls:
            return prior
        contents.append(response.candidates[0].content)

        submission = next((call for call in calls if call.name == SUBMIT_TOOL), None)
        if submission is not None:
            return _finish(prior, submission.args or {}, seen, queries, searches)

        # The API expects one response per function call in a turn, so every call is
        # answered, with an error when it cannot be run.
        tool_responses = []
        for call in calls:
            query = str((call.args or {}).get("query", "")).strip()
            if call.name != SEARCH_TOOL:
                answer: dict[str, Any] = {"error": f"unknown tool {call.name}"}
            elif not query:
                answer = {"error": "query is empty"}
            elif searches >= max_searches:
                answer = {"error": f"search budget used up; call {SUBMIT_TOOL}"}
            else:
                searches += 1
                queries.append(query)
                answer = _run_search(search, query, seen)
            tool_responses.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=call.id, name=call.name, response=answer
                    )
                )
            )
        contents.append(types.Content(role="user", parts=tool_responses))
    return prior


def _run_search(search: BookSearch, query: str, seen: dict[str, GoogleBook]) -> dict[str, Any]:
    try:
        result = search(query)
    except Exception as exc:
        # A catalog failure is reported to the model rather than ending the agent.
        logger.warning("Book resolution agent search failed: %s", type(exc).__name__)
        return {"error": "catalog search failed"}
    for book in result.books:
        seen[book.provider_volume_id] = book
    return {"status": result.status, "volumes": [_volume_view(book) for book in result.books]}


def _record_usage(usage: dict[str, int] | None, response: Any) -> None:
    metadata = getattr(response, "usage_metadata", None)
    if usage is None or metadata is None:
        return
    usage["calls"] = usage.get("calls", 0) + 1
    usage["input_tokens"] = usage.get("input_tokens", 0) + (metadata.prompt_token_count or 0)
    output = (metadata.candidates_token_count or 0) + (metadata.thoughts_token_count or 0)
    usage["output_tokens"] = usage.get("output_tokens", 0) + output


def _finish(
    prior: Resolution,
    args: dict[str, Any],
    seen: dict[str, GoogleBook],
    queries: list[str],
    searches: int,
) -> Resolution:
    volume_id = str(args.get("volume_id") or "").strip()
    reason = str(args.get("reason") or "").strip() or None
    base = {
        "candidates": prior.candidates,
        "queries": tuple(queries),
        "method": "agent",
        "searches": prior.searches + searches,
    }
    if not volume_id:
        return Resolution(status=prior.status, reason=reason, **base)
    book = seen.get(volume_id)
    if book is None:
        return Resolution(
            status=prior.status,
            reason=f"refused: agent chose a volume it never saw ({volume_id})",
            **base,
        )
    return Resolution(status="resolved", book=book, reason=reason, **base)
