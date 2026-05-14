from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from violet_assistant.config import Settings, load_settings
from violet_assistant.llm.factory import create_llm_provider
from violet_assistant.orchestrator.chat_orchestrator import ChatOrchestrator
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.personality.loader import PersonalityLoader
from violet_assistant.routes.chat import create_chat_router
from violet_assistant.routes.health import create_health_router
from violet_assistant.routes.memory import create_memory_router
from violet_assistant.routes.personality import create_personality_router


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or load_settings()
    migration_path = active_settings.repo_root / "database" / "migrations" / "001_init.sql"
    store = SQLiteStore.from_database_url(
        active_settings.database_url,
        base_dir=active_settings.repo_root,
        migration_path=migration_path,
    )
    store.initialize()

    personality_loader = PersonalityLoader(active_settings.personality_config_dir)
    provider = create_llm_provider(active_settings)
    orchestrator = ChatOrchestrator(
        settings=active_settings,
        provider=provider,
        personality_loader=personality_loader,
        store=store,
    )

    app = FastAPI(title="Violet Assistant Core", version="0.1.0")
    client_origins = {
        active_settings.public_client_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(client_origins),
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_health_router(active_settings, provider, personality_loader))
    app.include_router(create_personality_router(personality_loader))
    app.include_router(create_chat_router(orchestrator))
    app.include_router(create_memory_router(store))
    return app


app = create_app()
