from __future__ import annotations

import httpx


def fetch_html(url: str) -> tuple[str, dict]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        )
    }
    with httpx.Client(follow_redirects=True, headers=headers, timeout=20.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text, {
            "final_url": str(response.url),
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
        }

