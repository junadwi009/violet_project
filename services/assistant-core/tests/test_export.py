from __future__ import annotations

import inspect
import json
import re
import shutil
from dataclasses import fields, replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import violet_assistant.routes.export as export_module
from violet_assistant.config import load_settings
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.preferences.store import PreferencesStore
from violet_assistant.routes.export import create_export_router

# Every secret-bearing Settings field, by name shape. Matched as a whole
# `_`-delimited segment run so `gdrive_token_path` — a path to a file holding a
# live Google refresh token — is covered too; an `endswith` selector misses it.
# `database_url` is listed explicitly (rather than a generic "url" segment,
# which would also sweep in `public_client_url` — a non-secret browser URL)
# because a real deployment's DATABASE_URL can be a `postgresql://user:pass@host`
# connection string; this repo is SQLite-only today so the field is harmless in
# practice, but the selector should not depend on that staying true.
SECRET_FIELD_RE = re.compile(
    r"(?:^|_)(api_key|base_url|token|secrets?|password|credentials|database_url)(?:_|$)"
)

TEST_TOKEN = "task7b-correct-horse-battery"


class FakeMemoryStore:
    backend_name = "fake"

    def location(self) -> str:
        return "memory/"

    def list(self):
        return [{"id": "m1", "memory_type": "fact", "content": "likes tea"}]


@pytest.fixture()
def store(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    migration = repo_root / "database" / "migrations" / "001_init.sql"
    s = SQLiteStore(db_path=tmp_path / "test.db", migration_path=migration)
    s.initialize()
    s.ensure_session("s1", title="hello")
    s.add_message("s1", role="user", content="hi there")
    return s


def _get(router):
    for route in router.routes:
        if route.path == "/api/export":
            return route.endpoint
    raise KeyError("export")


@pytest.fixture()
def bundle_router(tmp_path, store):
    settings = load_settings(tmp_path)
    prefs = PreferencesStore(tmp_path / "preferences.json")
    prefs.patch({"theme": "dark"})
    return create_export_router(store, FakeMemoryStore(), prefs, settings)


@pytest.mark.asyncio
async def test_export_contains_user_data(bundle_router):
    response = await _get(bundle_router)()
    bundle = json.loads(response.body)

    assert bundle["schema_version"] == 1
    assert [s["id"] for s in bundle["sessions"]] == ["s1"]
    assert bundle["messages"][0]["content"] == "hi there"
    assert bundle["messages"][0]["session_id"] == "s1"
    assert bundle["memories"][0]["id"] == "m1"
    assert bundle["preferences"]["values"]["theme"] == "dark"
    assert bundle["preferences"]["overridden"] == ["theme"]


@pytest.mark.asyncio
async def test_export_is_an_attachment(bundle_router):
    response = await _get(bundle_router)()
    assert "attachment" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_export_excludes_locked_and_secrets(bundle_router):
    response = await _get(bundle_router)()
    bundle = json.loads(response.body)

    assert "locked" not in bundle
    assert "locked" not in bundle["preferences"]
    forbidden = re.compile(r"api_key|base_url|token|secret|password", re.I)
    assert not forbidden.search(response.body.decode("utf-8"))


@pytest.mark.asyncio
async def test_export_excludes_secret_values(tmp_path, store):
    """The name-based regex above only catches secrets under expected keys.

    A leak that relabels a field — e.g. ``{"endpoint": settings.llm_base_url,
    "credential": settings.llm_api_key}`` — slides right past it while still
    putting the live value in the bundle. Give every secret-bearing
    ``Settings`` field a distinctive canary value and assert none of those
    values appear anywhere in the serialized body, regardless of what key
    they might be filed under.

    The selector deliberately covers more than ``*_api_key`` / ``*_base_url``:
    ``gdrive_token_path`` names a file holding a live Google refresh token and
    was previously caught only by accident, because its *default value*
    happens to contain the word "token" and so tripped the name-based regex in
    ``test_export_excludes_locked_and_secrets``. Point ``GDRIVE_TOKEN_PATH``
    at a path without that word and an identical leak passed every test.

    ``database_url`` is covered too: this deployment is SQLite-only so the
    current value is harmless, but the field shape (a connection string that
    can embed a username/password) is exactly what this loop exists to catch,
    and it previously sat outside the selector entirely.
    """
    base_settings = load_settings(tmp_path)
    secret_field_names = [
        f.name for f in fields(base_settings) if SECRET_FIELD_RE.search(f.name)
    ]
    # Pinned so a newly added secret-bearing field can't silently join
    # Settings without also being covered by this loop.
    assert len(secret_field_names) == 22
    assert "gdrive_token_path" in secret_field_names
    assert "violet_api_token" in secret_field_names
    assert "database_url" in secret_field_names

    canaries = {name: f"CANARY-{name}-9f3a2b" for name in secret_field_names}
    settings = replace(base_settings, **canaries)

    prefs = PreferencesStore(tmp_path / "preferences.json")
    router = create_export_router(store, FakeMemoryStore(), prefs, settings)
    response = await _get(router)()
    body = response.body.decode("utf-8")

    for name, canary in canaries.items():
        assert canary not in body, f"secret value for {name!r} leaked into export bundle"


def _app_settings(tmp_path, token: str):
    """Settings for a throwaway `create_app()` — repo_root is `tmp_path`.

    `create_app()` builds its `PreferencesStore` at `<repo_root>/data/preferences.json`
    and opens the DB from `database_url`, so pointing repo_root at tmp_path keeps the
    developer's real preferences and database untouched; only the migration SQL is
    copied in. Same isolation pattern as
    `test_model_resolver.test_create_app_wires_the_resolver`.

    `violet_api_token` is always set explicitly (never inherited from the ambient
    environment) — the repo `.env` ships a `VIOLET_API_TOKEN` line, and
    `load_settings` `setdefault`s it into `os.environ`, so a test that relied on it
    being unset would pass or fail depending on which tests ran first.
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
        violet_api_token=token,
    )


def _client(tmp_path, token: str) -> TestClient:
    from violet_assistant.main import create_app

    return TestClient(create_app(_app_settings(tmp_path, token)))


def test_create_app_wires_the_export_router(tmp_path):
    """Pins `app.include_router(create_export_router(...))` in `main.create_app`.

    Most other tests in this file reach the handler by walking `router.routes`
    directly (see `_get` above), which never exercises `create_app()`, so the
    `include_router(create_export_router(...))` call could be deleted from
    `main.py` and those tests would stay green while `/api/export` silently
    vanished from the running app.
    """
    with _client(tmp_path, TEST_TOKEN) as client:
        response = client.get(
            "/api/export", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]


def test_export_is_disabled_when_no_token_is_configured(tmp_path):
    """Fail closed: an unconfigured token disables export, it does not open it.

    Any page on any localhost port can `fetch('/api/export')` cross-origin
    (the CORS policy allows every localhost origin with credentials), so an
    endpoint that hands over every session, message and memory in one GET must
    not be reachable until the user opts in.
    """
    with _client(tmp_path, "") as client:
        response = client.get("/api/export")
        with_header = client.get(
            "/api/export", headers={"Authorization": "Bearer anything"}
        )

    for res in (response, with_header):
        assert res.status_code == 503
        detail = res.json()["detail"]
        assert "VIOLET_API_TOKEN" in detail
        assert "disabled" in detail.lower()
        assert "sessions" not in res.text


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        TEST_TOKEN,  # no scheme
        f"Basic {TEST_TOKEN}",  # wrong scheme
        "Bearer",  # scheme only
        f"Bearer {TEST_TOKEN} extra",  # trailing junk
    ],
)
def test_export_rejects_missing_or_malformed_authorization(tmp_path, header):
    headers = {} if header is None else {"Authorization": header}
    with _client(tmp_path, TEST_TOKEN) as client:
        response = client.get("/api/export", headers=headers)

    assert response.status_code == 401
    assert "sessions" not in response.text


@pytest.mark.parametrize(
    "presented",
    [
        "wrong-token",
        TEST_TOKEN[:-1],  # correct prefix, truncated
        TEST_TOKEN + "x",  # correct prefix, extended
        TEST_TOKEN.upper(),  # case must matter
        f" {TEST_TOKEN}",
    ],
)
def test_export_rejects_a_wrong_bearer_token(tmp_path, presented):
    with _client(tmp_path, TEST_TOKEN) as client:
        response = client.get(
            "/api/export", headers={"Authorization": f"Bearer {presented}"}
        )

    assert response.status_code == 401
    assert "sessions" not in response.text


def test_export_serves_the_unchanged_bundle_with_the_correct_token(tmp_path):
    with _client(tmp_path, TEST_TOKEN) as client:
        response = client.get(
            "/api/export", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="violet-export-'
    )
    bundle = response.json()
    assert bundle["schema_version"] == 1
    assert set(bundle) == {
        "exported_at",
        "schema_version",
        "sessions",
        "messages",
        "memories",
        "preferences",
    }


def test_rejection_bodies_never_echo_the_configured_token(tmp_path):
    """A 401/503 that quotes the expected token turns the gate into an oracle."""
    responses = []
    with _client(tmp_path, TEST_TOKEN) as client:
        responses.append(client.get("/api/export"))
        responses.append(
            client.get("/api/export", headers={"Authorization": "Bearer nope"})
        )
    with _client(tmp_path, "") as client:
        responses.append(client.get("/api/export"))

    for res in responses:
        body = res.text
        assert TEST_TOKEN not in body
        for size in (8, 12, 16):
            assert TEST_TOKEN[:size] not in body


def test_export_source_pins_constant_time_comparison(tmp_path):
    """Static pin on `hmac.compare_digest`, anchored to the comparison itself.

    Honest scope: this asserts on source text, not behavior. A timing side
    channel is not observable from a test process with any reliability, so
    there is no behavioral test that distinguishes `compare_digest` from `==`
    or `!=`. What this catches is a refactor quietly swapping the
    constant-time comparison back out — it proves nothing about actual
    timing, hence the name: it pins source shape, not behavior.

    Anchored to the comparison statement, not "compare_digest appears
    somewhere in the module": an earlier version only asserted presence of
    the literal `hmac.compare_digest(` plus the absence of
    `== settings.violet_api_token`. Both of those survive a mutation that (a)
    adds an unused decoy `hmac.compare_digest(b"decoy", b"decoy")` call
    elsewhere and (b) rewrites the real check to compare the local `expected`
    /`presented` variables with `!=` instead of `settings.violet_api_token`
    directly — the decoy satisfies the positive assertion and the real
    rewrite never matches the `settings.violet_api_token` pattern the
    negative assertion was looking for. Requiring `compare_digest(...)` to
    take `presented` and `expected` as its own arguments, in the same
    statement, closes that gap.
    """
    source = inspect.getsource(export_module)
    comparison = re.search(
        r"hmac\.compare_digest\(\s*presented\.encode\([^)]*\)\s*,"
        r"\s*expected\.encode\([^)]*\)\s*\)",
        source,
    )
    assert comparison, (
        "expected the token check to call "
        "hmac.compare_digest(presented.encode(...), expected.encode(...)) "
        "as the actual comparison"
    )
    assert not re.search(r"\bpresented\s*(==|!=)\s*expected\b", source)
    assert not re.search(r"\bexpected\s*(==|!=)\s*presented\b", source)
