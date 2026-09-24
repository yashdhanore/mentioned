"""Local stand-ins for the providers the worker calls, faked at the network or process boundary.

- `FakeGemini` speaks the real `generateContent` wire format; the real google-genai SDK reaches
  it through `GOOGLE_GEMINI_BASE_URL`, so the SDK's own response handling is under test.
- `FakeGoogleBooks` speaks the Books `volumes` search format; the real `search_volumes` reaches
  it once a suite points `src.extraction.google_books.GOOGLE_BOOKS_API` at it (the module has
  no configurable base URL, and the worker runs in the test process).
- `FakeYtDlp` puts `fake_yt_dlp.py` first on PATH as `yt-dlp`, so the real download code runs
  but nothing is fetched from Instagram.
- `FakeLangfuse` accepts the OTLP trace exports and score batches the real Langfuse SDK sends,
  and decodes them, so a suite can check exactly what would have left the process.

Each fake records what it was asked, so a scenario can check which calls happened.
"""

from __future__ import annotations

import base64
import contextlib
import gzip
import json
import os
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest


class _LocalServer:
    """A threaded HTTP server on a free local port, started and stopped by a fixture."""

    def __init__(self, handler: type[BaseHTTPRequestHandler]) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


DEFAULT_USAGE = {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15}


def gemini_text_reply(
    text: str, finish_reason: str = "STOP", usage: dict[str, Any] | None = None
) -> dict[str, Any]:
    """A `generateContent` response whose only candidate answers `text`."""
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": text}]},
                "finishReason": finish_reason,
                "index": 0,
            }
        ],
        "usageMetadata": usage or DEFAULT_USAGE,
    }


def gemini_mentions_reply(
    mentions: list[dict[str, Any]], usage: dict[str, Any] | None = None
) -> dict[str, Any]:
    return gemini_text_reply(json.dumps({"mentions": mentions}), usage=usage)


def gemini_gate_reply(verdict: str, reason: str) -> dict[str, Any]:
    return gemini_text_reply(json.dumps({"verdict": verdict, "reason": reason}))


RELEVANT_GATE = gemini_gate_reply("relevant", "fake gate")


def _request_text(payload: dict[str, Any]) -> str:
    """The text parts plus the decoded inline media of a `generateContent` request."""
    chunks: list[str] = []
    for content in payload.get("contents") or []:
        for part in content.get("parts") or []:
            if isinstance(part.get("text"), str):
                chunks.append(part["text"])
            inline = part.get("inlineData") or part.get("inline_data") or {}
            if isinstance(inline.get("data"), str):
                # binascii.Error, raised for bad base64, is a ValueError.
                with contextlib.suppress(ValueError):
                    chunks.append(base64.b64decode(inline["data"]).decode("utf-8", "replace"))
    return "\n".join(chunks)


class FakeGemini(_LocalServer):
    """Answers each model with a set reply, or with a per-Reel reply when the request carries a
    registered Reel marker (in the caption the gate sees, or in the media extraction sees), so
    one worker run can process several Reels that each need their own answer."""

    # The worker must be configured with these as GEMINI_MODEL and GEMINI_GATE_MODEL.
    extraction_model = "fake-extraction-model"
    gate_model = "fake-gate-model"

    def __init__(self, *, extraction_model: str | None = None, gate_model: str | None = None):
        if extraction_model:
            self.extraction_model = extraction_model
        if gate_model:
            self.gate_model = gate_model
        self.replies: dict[str, dict[str, Any]] = {}
        self.reel_replies: dict[str, dict[str, dict[str, Any]]] = {}
        # Per model, HTTP error statuses to answer, in order, before the set reply.
        self.failures: dict[str, list[int]] = {}
        self.requests: list[str] = []
        self.calls: list[dict[str, str | None]] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                # Path shape: /v1beta/models/<model>:generateContent
                model = self.path.split("/models/", 1)[-1].split(":", 1)[0]
                try:
                    request_text = _request_text(json.loads(raw or b"{}"))
                except ValueError:
                    request_text = ""
                reel = next((m for m in fake.reel_replies if m in request_text), None)
                fake.requests.append(model)
                fake.calls.append({"model": model, "reel": reel})
                pending = fake.failures.get(model)
                if pending:
                    status = pending.pop(0)
                    _send_json(self, status, {"error": {"code": status, "message": "fake"}})
                    return
                reply = fake.reel_replies.get(reel, {}).get(model) or fake.replies.get(model)
                if reply is None:
                    _send_json(self, 500, {"error": "no reply set"})
                else:
                    _send_json(self, 200, reply)

            def log_message(self, *_args) -> None:
                pass

        super().__init__(Handler)

    def reply(self, *, extraction: dict[str, Any], gate: dict[str, Any] | None = None) -> None:
        """Answer every request per model, and forget earlier requests."""
        self.replies = {self.extraction_model: extraction, self.gate_model: gate or RELEVANT_GATE}
        self.failures = {}
        self.requests = []
        self.calls = []

    def fail_next(self, model: str, status: int, times: int = 1) -> None:
        """Answer the next `times` requests to `model` with HTTP `status`."""
        self.failures.setdefault(model, []).extend([status] * times)

    def reply_for_reel(
        self, marker: str, *, extraction: dict[str, Any], gate: dict[str, Any] | None = None
    ) -> None:
        self.reel_replies[marker] = {
            self.extraction_model: extraction,
            self.gate_model: gate or RELEVANT_GATE,
        }

    def models_called_for(self, marker: str) -> list[str]:
        return [call["model"] for call in self.calls if call["reel"] == marker]


class FakeGoogleBooks(_LocalServer):
    """Serves `GET /books/v1/volumes?q=...` with a set result per exact query; any other query
    finds nothing."""

    PATH = "/books/v1/volumes"

    def __init__(self) -> None:
        self.results: dict[str, tuple[int, dict[str, Any]]] = {}
        self.requests: list[dict[str, str | None]] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parts = urlsplit(self.path)
                params = {key: values[0] for key, values in parse_qs(parts.query).items()}
                fake.requests.append(
                    {
                        "path": parts.path,
                        "q": params.get("q"),
                        "key": params.get("key"),
                        "maxResults": params.get("maxResults"),
                    }
                )
                empty = (200, {"kind": "books#volumes", "totalItems": 0})
                status, payload = fake.results.get(params.get("q", ""), empty)
                if parts.path != FakeGoogleBooks.PATH:
                    status, payload = 404, {"error": "unknown path"}
                _send_json(self, status, payload)

            def log_message(self, *_args) -> None:
                pass

        super().__init__(Handler)
        self.api_url = self.base_url + self.PATH

    def volumes(self, query: str, volumes: list[dict[str, Any]]) -> None:
        self.results[query] = (
            200,
            {"kind": "books#volumes", "totalItems": len(volumes), "items": volumes},
        )

    def outage(self, query: str, status: int = 500) -> None:
        self.results[query] = (status, {"error": {"code": status, "message": "fake outage"}})

    def queries(self) -> list[str | None]:
        return [request["q"] for request in self.requests]


def _otlp_value(value: Any) -> Any:
    kind = value.WhichOneof("value")
    if kind == "array_value":
        return [_otlp_value(item) for item in value.array_value.values]
    if kind == "kvlist_value":
        return {item.key: _otlp_value(item.value) for item in value.kvlist_value.values}
    return getattr(value, kind) if kind else None


def _otlp_attributes(attributes: Any) -> dict[str, Any]:
    return {item.key: _otlp_value(item.value) for item in attributes}


def _json_or_raw(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return value


class ExportedSpan:
    """One span as the Langfuse SDK exported it, with the Langfuse attributes decoded."""

    METADATA_PREFIX = "langfuse.observation.metadata."

    def __init__(self, span: Any, resource: dict[str, Any], scope: str) -> None:
        self.name: str = span.name
        self.trace_id: str = span.trace_id.hex()
        self.span_id: str = span.span_id.hex()
        self.parent_span_id: str | None = span.parent_span_id.hex() or None
        self.attributes = _otlp_attributes(span.attributes)
        self.resource = resource
        self.scope = scope

    def _get(self, key: str) -> Any:
        return _json_or_raw(self.attributes.get(key))

    @property
    def type(self) -> str | None:
        return self.attributes.get("langfuse.observation.type")

    @property
    def level(self) -> str:
        return self.attributes.get("langfuse.observation.level") or "DEFAULT"

    @property
    def status_message(self) -> str | None:
        return self.attributes.get("langfuse.observation.status_message")

    @property
    def input(self) -> Any:
        return self._get("langfuse.observation.input")

    @property
    def output(self) -> Any:
        return self._get("langfuse.observation.output")

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            key.removeprefix(self.METADATA_PREFIX): _json_or_raw(value)
            for key, value in self.attributes.items()
            if key.startswith(self.METADATA_PREFIX)
        }

    @property
    def model(self) -> str | None:
        return self.attributes.get("langfuse.observation.model.name")

    @property
    def usage(self) -> dict[str, Any] | None:
        return self._get("langfuse.observation.usage_details")

    @property
    def cost(self) -> dict[str, Any] | None:
        return self._get("langfuse.observation.cost_details")

    @property
    def session_id(self) -> str | None:
        return self.attributes.get("session.id")

    @property
    def user_id(self) -> str | None:
        return self.attributes.get("user.id")

    @property
    def tags(self) -> list[str]:
        return list(self.attributes.get("langfuse.trace.tags") or [])

    @property
    def trace_name(self) -> str | None:
        return self.attributes.get("langfuse.trace.name")

    @property
    def environment(self) -> str | None:
        # The SDK stamps each span with its client's environment; the resource attribute
        # belongs to the process-wide tracer provider, which the first client creates.
        return self.attributes.get("langfuse.environment") or self.resource.get(
            "langfuse.environment"
        )


class FakeLangfuse(_LocalServer):
    """Langfuse Cloud's ingestion endpoints: OTLP trace exports (protobuf) and score batches.

    `status` other than 200 makes every request fail, to stand in for an outage."""

    OTEL_PATH = "/api/public/otel/v1/traces"
    INGESTION_PATH = "/api/public/ingestion"

    def __init__(self, status: int = 200) -> None:
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
            ExportTraceServiceRequest,
            ExportTraceServiceResponse,
        )

        self.status = status
        self.bodies: list[bytes] = []
        self.spans: list[ExportedSpan] = []
        self.scores: list[dict[str, Any]] = []
        self.authorizations: set[str | None] = set()
        self.lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if self.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                with fake.lock:
                    fake.bodies.append(body)
                    fake.authorizations.add(self.headers.get("Authorization"))
                if fake.status != 200:
                    _send_json(self, fake.status, {"error": "fake outage"})
                    return
                if self.path == FakeLangfuse.OTEL_PATH:
                    request = ExportTraceServiceRequest()
                    request.ParseFromString(body)
                    spans = [
                        ExportedSpan(span, _otlp_attributes(rs.resource.attributes), ss.scope.name)
                        for rs in request.resource_spans
                        for ss in rs.scope_spans
                        for span in ss.spans
                    ]
                    with fake.lock:
                        fake.spans.extend(spans)
                    reply = ExportTraceServiceResponse().SerializeToString()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-protobuf")
                    self.send_header("Content-Length", str(len(reply)))
                    self.end_headers()
                    self.wfile.write(reply)
                    return
                if self.path == FakeLangfuse.INGESTION_PATH:
                    batch = json.loads(body or b"{}").get("batch") or []
                    with fake.lock:
                        fake.scores.extend(
                            event["body"] for event in batch if event.get("type") == "score-create"
                        )
                    _send_json(self, 207, {"successes": [], "errors": []})
                    return
                _send_json(self, 404, {"error": "unknown path"})

            def do_GET(self) -> None:
                # The SDK may look up its project; nothing a suite checks depends on it.
                _send_json(self, 200, {"data": [{"id": "e2e-project", "name": "e2e"}]})

            def log_message(self, *_args) -> None:
                pass

        super().__init__(Handler)

    def spans_in_session(self, session_id: str) -> list[ExportedSpan]:
        with self.lock:
            return [span for span in self.spans if span.session_id == session_id]

    def scores_for_trace(self, trace_id: str) -> list[dict[str, Any]]:
        with self.lock:
            return [score for score in self.scores if score.get("traceId") == trace_id]

    def everything_sent(self) -> bytes:
        with self.lock:
            return b"".join(self.bodies)


class FakeYtDlp:
    """A `yt-dlp` on PATH that serves registered fake Reels (see `fake_yt_dlp.py`)."""

    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.bin_dir = directory / "bin"
        self.bin_dir.mkdir(exist_ok=True)
        self.catalog_path = directory / "catalog.json"
        self.log_path = directory / "calls.jsonl"
        self.catalog: dict[str, dict[str, Any]] = {}
        self._write_catalog()
        self.log_path.write_text("")
        script = Path(__file__).with_name("fake_yt_dlp.py")
        launcher = self.bin_dir / "yt-dlp"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.executable = str(launcher)

    def _write_catalog(self) -> None:
        self.catalog_path.write_text(json.dumps(self.catalog))

    def add(
        self,
        shortcode: str,
        *,
        caption: str,
        creator: str,
        duration_seconds: float = 42.0,
        error: str | None = None,
    ) -> None:
        """Register a Reel. Its media bytes and caption both carry the shortcode, which is the
        marker `FakeGemini` answers by."""
        self.catalog[shortcode] = {
            "metadata": {
                "id": shortcode,
                "title": f"Video by {creator}",
                "description": caption,
                "channel": creator,
                "uploader": creator.replace(".", " ").title(),
                "uploader_id": "1234567890",
                "duration": duration_seconds,
            },
            "media": f"e2e fake reel media {shortcode}",
            "error": error,
        }
        self._write_catalog()

    def set_error(self, shortcode: str, error: str | None) -> None:
        self.catalog[shortcode]["error"] = error
        self._write_catalog()

    def calls(self, shortcode: str | None = None) -> list[dict[str, str]]:
        calls = [json.loads(line) for line in self.log_path.read_text().splitlines() if line]
        return [call for call in calls if shortcode is None or call["shortcode"] == shortcode]

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PATH", f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
        monkeypatch.setenv("E2E_FAKE_YT_DLP_CATALOG", str(self.catalog_path))
        monkeypatch.setenv("E2E_FAKE_YT_DLP_LOG", str(self.log_path))
