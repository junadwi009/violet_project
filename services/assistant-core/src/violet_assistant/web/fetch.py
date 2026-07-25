from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib import error, request
from urllib.parse import urlparse

_SKIP_TAGS = {"script", "style", "noscript", "head"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def text(self) -> str:
        return "\n".join(self._parts)


def extract_text(html: str) -> tuple[str, str]:
    """Return (title, readable_text) from an HTML string. Scripts/styles dropped."""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.title.strip(), parser.text()


def is_blocked_host(host: str) -> bool:
    """True for hosts that resolve to loopback/private/link-local/reserved ranges (SSRF guard)."""
    host = host.strip("[]").lower()
    if host in {"localhost", ""}:
        return True
    candidates: list[str] = [host]
    try:
        candidates = [info[4][0] for info in socket.getaddrinfo(host, None)]
    except socket.gaierror:
        pass
    for addr in candidates:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


@dataclass(frozen=True)
class FetchResult:
    url: str
    title: str
    text: str
    chars: int
    truncated: bool


def fetch_url(url: str, max_bytes: int = 2_000_000) -> FetchResult:
    """Fetch an http(s) URL and extract readable text. Raises ValueError on bad/blocked URLs."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http(s) URLs are allowed")
    if not parsed.hostname or is_blocked_host(parsed.hostname):
        raise ValueError("host is not allowed")
    req = request.Request(url, headers={"User-Agent": "VioletAssistant/0.1"})
    try:
        with request.urlopen(req, timeout=15) as resp:
            raw = resp.read(max_bytes + 1)
    except error.URLError as exc:
        raise ValueError(f"could not fetch: {exc.reason}") from exc
    truncated = len(raw) > max_bytes
    html = raw[:max_bytes].decode("utf-8", errors="replace")
    title, text = extract_text(html)
    return FetchResult(url=url, title=title, text=text, chars=len(text), truncated=truncated)
