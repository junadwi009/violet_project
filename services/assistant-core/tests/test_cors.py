"""CORS policy pins for the assistant-core app (Task 7c).

The app used to configure `CORSMiddleware` with an explicit `client_origins`
allowlist *and* `allow_origin_regex=r"http://(localhost|127\\.0\\.0\\.1):\\d+"`.
The regex made the allowlist decorative: every localhost port was allowed, with
credentials. Any page served from any local port — a second dev server, a local
Electron app, an npm postinstall that opens a listener — could read the response
of any endpoint, including `GET /api/sessions`, `GET /api/memory` and
`GET /api/sessions/{id}/messages` (which together reproduce the export bundle
that Task 7b put behind a token), and could fire `DELETE /api/sessions` as a
single destructive cross-origin call.

These tests are written against the real `create_app()` so they exercise the
middleware as it is actually wired, and they are the regression net for the
`allow_origin_regex` argument specifically: restore that line and the
arbitrary-localhost-port cases below must fail.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from violet_assistant.config import load_settings

ALLOWED_ORIGIN = "http://127.0.0.1:5173"
PUBLIC_CLIENT_URL = "http://localhost:5173"

# Origins that must NOT be echoed back. The localhost ones are the point of this
# task: they are exactly what `allow_origin_regex` used to wave through.
DISALLOWED_ORIGINS = [
    "http://localhost:31337",
    "http://127.0.0.1:31337",
    # A neighbor of the allowlisted `vite preview` port (4173, see
    # `test_allowed_origin_is_echoed`) that must still be rejected — proves the
    # allowlist admits exactly 4173, not every port near it.
    "http://localhost:4174",
    "https://evil.example",
    "http://evil.example",
]


def _app_settings(tmp_path: Path):
    """Settings for a throwaway `create_app()` — repo_root is `tmp_path`.

    Same isolation pattern as `test_export._app_settings`: pointing repo_root at
    tmp_path keeps the developer's real preferences file and database untouched;
    only the migration SQL is copied in.

    `public_client_url` is pinned explicitly rather than inherited from the
    ambient environment — `load_settings` reads the repo `.env`, so a test that
    depended on the ambient `PUBLIC_CLIENT_URL` would pass or fail depending on
    what is in that (git-ignored, machine-local) file.
    """
    repo_root = Path(__file__).resolve().parents[3]
    migrations = tmp_path / "database" / "migrations"
    migrations.mkdir(parents=True, exist_ok=True)
    for name in ("001_init.sql", "002_agent_runs.sql"):
        shutil.copy(repo_root / "database" / "migrations" / name, migrations / name)

    return replace(
        load_settings(tmp_path),
        repo_root=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'violet.db'}",
        memory_dir=tmp_path / "memory",
        rag_provider="none",
        public_client_url=PUBLIC_CLIENT_URL,
        violet_api_token="",
    )


@pytest.fixture()
def client(tmp_path) -> TestClient:
    from violet_assistant.main import create_app

    with TestClient(create_app(_app_settings(tmp_path))) as test_client:
        yield test_client


def _preflight(client: TestClient, path: str, origin: str, method: str, headers: str = ""):
    request_headers = {
        "Origin": origin,
        "Access-Control-Request-Method": method,
    }
    if headers:
        request_headers["Access-Control-Request-Headers"] = headers
    return client.options(path, headers=request_headers)


# --- allowed origins -------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    [
        ALLOWED_ORIGIN,
        PUBLIC_CLIENT_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # `npm run preview` (vite preview) does not honor `server.port` and
        # serves on 4173 by default — a legitimate, repo-shipped way of
        # serving the client, so it must be allowlisted.
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
)
def test_allowed_origin_is_echoed(client, origin):
    response = client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_public_client_url_is_allowed(tmp_path):
    """`PUBLIC_CLIENT_URL` must still feed the allowlist.

    Pinned with a value that is *not* one of the hardcoded localhost entries, so
    dropping `active_settings.public_client_url` from `client_origins` fails here
    instead of being masked by the 3000/5173 literals.
    """
    from violet_assistant.main import create_app

    origin = "http://violet.local:9999"
    settings = replace(_app_settings(tmp_path), public_client_url=origin)
    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/health", headers={"Origin": origin})

    assert response.headers.get("access-control-allow-origin") == origin


def test_preflight_from_an_allowed_origin_still_permits_authorization(client):
    """`allow_headers=["*"]` must keep permitting `Authorization`.

    `GET /api/export` (Task 7b) is gated on an `Authorization: Bearer` header,
    which is not CORS-safelisted, so the browser preflights it. Dropping
    `allow_credentials` must not break that.
    """
    response = _preflight(
        client, "/api/export", ALLOWED_ORIGIN, "GET", headers="authorization"
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    allowed = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed or allowed == "*"


# --- disallowed origins ----------------------------------------------------


@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
@pytest.mark.parametrize(
    "path", ["/health", "/api/sessions", "/api/memory", "/api/export"]
)
def test_disallowed_origin_is_not_echoed(client, origin, path):
    """No `Access-Control-Allow-Origin` for an origin outside the allowlist.

    Without that header the browser refuses to hand the response body to the
    calling page, so the three ungated read endpoints stop being cross-origin
    readable even though they remain unauthenticated.
    """
    response = client.get(path, headers={"Origin": origin})

    assert "access-control-allow-origin" not in response.headers
    assert response.headers.get("access-control-allow-origin") != origin
    assert response.headers.get("access-control-allow-origin") != "*"


@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
def test_preflight_for_destructive_delete_is_refused(client, origin):
    """`DELETE /api/sessions` wipes every session and message.

    It is unauthenticated, so the preflight is the only thing standing between a
    hostile local page and a one-request data wipe.
    """
    response = _preflight(client, "/api/sessions", origin, "DELETE")

    # Starlette answers a refused preflight with 400 "Disallowed CORS origin".
    # It still emits `Access-Control-Allow-Methods` on that response, so the
    # load-bearing signal — the one the browser actually gates on — is the
    # *absence* of `Access-Control-Allow-Origin`.
    assert response.status_code == 400
    assert "Disallowed CORS origin" in response.text
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
def test_preflight_for_export_is_refused(client, origin):
    response = _preflight(client, "/api/export", origin, "GET", headers="authorization")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


# --- credentials -----------------------------------------------------------


def test_credentials_are_not_allowed(client):
    """Nothing here authenticates with cookies.

    The only credential is the Task 7b `Authorization: Bearer` header, which is
    unaffected by this flag. `allow_credentials=True` alongside
    `allow_headers=["*"]` is also a spec violation browsers handle
    inconsistently.
    """
    simple = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    preflight = _preflight(
        client, "/api/export", ALLOWED_ORIGIN, "GET", headers="authorization"
    )

    for response in (simple, preflight):
        assert "access-control-allow-credentials" not in response.headers


# --- source pin ------------------------------------------------------------


def test_main_source_passes_no_origin_regex():
    """Static pin on the absence of an `allow_origin_regex` argument.

    The behavioral tests above cover the ports they name, but an allowlist is a
    closed set and a regex is not — a *differently shaped* regex (say
    `r"http://.*"`) would be caught by them only where it happens to overlap the
    origins they enumerate. This asserts the argument is simply not there, which
    is the actual design decision: `client_origins` is the single source of
    allowed origins.

    Comments are tokenized out first, so the explanatory comment in `main.py`
    (which names the argument in order to say why it is gone) does not satisfy
    the check, and so that comment cannot be quietly replaced by real code.
    """
    import inspect
    import io
    import tokenize

    import violet_assistant.main as main_module

    source = inspect.getsource(main_module)
    code = "".join(
        token.string if token.type != tokenize.COMMENT else ""
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
    )
    assert "allow_origin_regex" not in code
    # ...and the comment really is the only place the name survives, i.e. this
    # test is checking something rather than passing vacuously.
    assert "allow_origin_regex" in source
