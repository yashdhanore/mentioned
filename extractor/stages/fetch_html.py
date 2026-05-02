from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from extractor.stages.normalize_url import INSTAGRAM_HOSTS, SourceUrlError


MAX_REDIRECTS = 3
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _host_resolves_to_blocked_network(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SourceUrlError("Source host could not be resolved") from exc
    for info in infos:
        address = info[4][0]
        ip_address = ipaddress.ip_address(address)
        if any(ip_address in network for network in BLOCKED_NETWORKS):
            return True
    return False


def _validate_fetch_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise SourceUrlError("Only HTTPS source fetches are allowed")
    hostname = parts.hostname.lower() if parts.hostname else ""
    if hostname not in INSTAGRAM_HOSTS:
        raise SourceUrlError("Redirect target is not an allowed Instagram host", error_code="unsupported_source_kind")
    if _host_resolves_to_blocked_network(hostname):
        raise SourceUrlError("Source host resolved to a blocked network")


def fetch_html(url: str) -> tuple[str, dict]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        )
    }
    current_url = url
    with httpx.Client(follow_redirects=False, headers=headers, timeout=20.0) as client:
        for redirect_count in range(MAX_REDIRECTS + 1):
            _validate_fetch_url(current_url)
            response = client.get(current_url)
            if response.is_redirect:
                if redirect_count == MAX_REDIRECTS:
                    raise SourceUrlError("Too many redirects while fetching source")
                location = response.headers.get("location")
                if not location:
                    raise SourceUrlError("Redirect response did not include a location")
                current_url = urljoin(current_url, location)
                continue
            response.raise_for_status()
            return response.text, {
                "final_url": str(response.url),
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "redirect_count": redirect_count,
            }
    raise SourceUrlError("Source fetch failed")
