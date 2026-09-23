"""A stand-in for the `yt-dlp` binary, so an E2E run never downloads anything from Instagram.

`tests/e2e/fakes.py` puts a `yt-dlp` launcher for this script first on PATH, so the worker's
real `src/extraction/download.py` runs it exactly as it runs yt-dlp: once with
`--dump-single-json --skip-download` for the metadata, then once to download the media into
the `-o` template and print the file path. Each fake Reel is looked up by its shortcode in the
JSON catalog named by `E2E_FAKE_YT_DLP_CATALOG`; an unknown Reel fails like yt-dlp does, with
an `ERROR:` line and exit code 1, and never falls through to the real binary. Every call is
appended to the JSON-lines log named by `E2E_FAKE_YT_DLP_LOG`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|p)/([^/?#]+)")


def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    catalog_path = os.environ.get("E2E_FAKE_YT_DLP_CATALOG")
    log_path = os.environ.get("E2E_FAKE_YT_DLP_LOG")
    if not catalog_path or not log_path or not argv:
        return _fail("[e2e fake yt-dlp] run only by the E2E suites")

    url = argv[-1]
    match = SHORTCODE_RE.search(url)
    shortcode = match.group(1) if match else ""
    mode = "metadata" if "--dump-single-json" in argv else "download"
    with open(log_path, "a") as log:
        log.write(json.dumps({"mode": mode, "shortcode": shortcode, "url": url}) + "\n")

    reel = json.loads(Path(catalog_path).read_text()).get(shortcode)
    if reel is None:
        return _fail(f"[e2e fake yt-dlp] no fake Reel registered for {url}")
    if reel.get("error"):
        return _fail(reel["error"])
    if mode == "metadata":
        print(json.dumps(reel["metadata"]))
        return 0

    template = argv[argv.index("-o") + 1]
    media = Path(template.replace("%(autonumber)03d", "001").replace("%(ext)s", "mp4"))
    media.write_bytes(reel["media"].encode())
    print(media)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
