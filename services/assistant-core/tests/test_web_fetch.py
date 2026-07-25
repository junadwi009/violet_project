from __future__ import annotations

import pytest

from violet_assistant.routes.fetch import FetchRequest, create_fetch_router
from violet_assistant.web.fetch import extract_text, is_blocked_host


def test_extract_text_strips_scripts_and_reads_title():
    html = (
        "<html><head><title>Hi</title></head>"
        "<body><p>Hello</p><script>bad()</script></body></html>"
    )
    title, text = extract_text(html)
    assert title == "Hi"
    assert "Hello" in text
    assert "bad()" not in text


@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.1.1", "::1"],
)
def test_blocks_internal_hosts(host):
    assert is_blocked_host(host) is True


def test_allows_public_host():
    assert is_blocked_host("example.com") is False


def _post_endpoint(router):
    for route in router.routes:
        if "POST" in route.methods:
            return route.endpoint
    raise KeyError("POST")


@pytest.mark.asyncio
async def test_fetch_endpoint_blocks_localhost():
    from fastapi import HTTPException

    endpoint = _post_endpoint(create_fetch_router())
    with pytest.raises(HTTPException) as exc_info:
        await endpoint(FetchRequest(url="http://127.0.0.1:8000/secret"))
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_endpoint_rejects_non_http_scheme():
    from fastapi import HTTPException

    endpoint = _post_endpoint(create_fetch_router())
    with pytest.raises(HTTPException) as exc_info:
        await endpoint(FetchRequest(url="file:///etc/passwd"))
    assert exc_info.value.status_code == 400
