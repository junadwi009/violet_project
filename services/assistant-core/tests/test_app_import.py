from __future__ import annotations

import importlib
import sys

import pytest


def _fresh_main():
    """Re-import violet_assistant.main from scratch."""
    sys.modules.pop("violet_assistant.main", None)
    return importlib.import_module("violet_assistant.main")


def test_importing_main_does_not_build_the_app():
    """Regression: importing the module must not run create_app().

    `app = create_app()` at module scope meant that any test importing this
    module executed the whole app factory with the developer's real .env — and
    so migrated/opened the real data/violet.db. The app must be built lazily.
    """
    module = _fresh_main()
    assert "app" not in vars(module), (
        "importing violet_assistant.main built the app (and touched the real DB)"
    )
    assert callable(module.create_app)


def test_app_attribute_is_still_available_for_uvicorn(tmp_path, monkeypatch):
    """`uvicorn violet_assistant.main:app` must keep working — it does getattr(module, 'app')."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'v.db'}")
    monkeypatch.setenv("MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("KNOWLEDGE_DB", str(tmp_path / "knowledge.db"))
    monkeypatch.setenv("KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    module = _fresh_main()

    app = module.app  # the access uvicorn performs

    assert app.__class__.__name__ == "FastAPI"
    # cached after first access, so uvicorn workers don't rebuild per lookup
    assert module.app is app
    assert "app" in vars(module)


def test_unknown_attribute_still_raises():
    module = _fresh_main()
    with pytest.raises(AttributeError):
        module.does_not_exist
