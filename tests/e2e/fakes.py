"""Local stand-ins for the providers the worker calls, faked at the network or process boundary.

- `FakeGemini` speaks the real `generateContent` wire format; the real google-genai SDK reaches
  it through `GOOGLE_GEMINI_BASE_URL`, so the SDK's own response handling is under test.
- `FakeGoogleBooks` speaks the Books `volumes` search format; the real `search_volumes` reaches
  it once a suite points `src.extraction.google_books.GOOGLE_BOOKS_API` at it (the module has
  no configurable base URL, and the worker runs in the test process).
- `FakeYtDlp` puts `fake_yt_dlp.py` first on PATH as `yt-dlp`, so the real download code runs
  but nothing is fetched from Instagram.

Each fake records what it was asked, so a scenario can check which calls happened.
"""

from __future__ import annotations

import base64
import contextlib
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


def gemini_text_reply(text: str, finish_reason: str = "STOP") -> dict[str, Any]:
    """A `generateContent` response whose only candidate answers `text`."""
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": text}]},
                "finishReason": finish_reason,
                "index": 0,
            }
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
    }


def gemini_mentions_reply(mentions: list[dict[str, Any]]) -> dict[str, Any]:
    return gemini_text_reply(json.dumps({"mentions": mentions}))


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

    def __init__(self) -> None:
        self.replies: dict[str, dict[str, Any]] = {}
        self.reel_replies: dict[str, dict[str, dict[str, Any]]] = {}
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
        self.requests = []
        self.calls = []

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
