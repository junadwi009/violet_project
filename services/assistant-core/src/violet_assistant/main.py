from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from violet_assistant.config import Settings, load_settings
from violet_assistant.llm.factory import create_llm_provider
from violet_assistant.llm.registry import build_provider_registry
from violet_assistant.memory.store.factory import (
    create_approved_memory_store,
    migrate_sqlite_memories_to_files,
)
from violet_assistant.memory.store.file_store import FileApprovedMemoryStore
from violet_assistant.orchestrator.cascade import CascadeResponder, build_layer_configs
from violet_assistant.orchestrator.chat_orchestrator import ChatOrchestrator
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.personality.loader import PersonalityLoader
from violet_assistant.rag.factory import create_retriever
from violet_assistant.routes.chat import create_chat_router
from violet_assistant.routes.health import create_health_router
from violet_assistant.routes.memory import create_memory_router
from violet_assistant.routes.personality import create_personality_router
from violet_assistant.routes.providers import create_providers_router
from violet_assistant.routes.sessions import create_sessions_router
from violet_assistant.routes.skills import create_skills_router
from violet_assistant.llm.openai_compatible_provider import OpenAICompatibleProvider
from violet_assistant.skills.generator import SkillEngine
from violet_assistant.skills.registry import SkillRegistry


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or load_settings()
    migration_path = active_settings.repo_root / "database" / "migrations" / "001_init.sql"
    store = SQLiteStore.from_database_url(
        active_settings.database_url,
        base_dir=active_settings.repo_root,
        migration_path=migration_path,
    )
    store.initialize()

    memory_store = create_approved_memory_store(active_settings, store)
    if isinstance(memory_store, FileApprovedMemoryStore):
        migrate_sqlite_memories_to_files(store, memory_store)

    personality_loader = PersonalityLoader(active_settings.personality_config_dir)
    provider = create_llm_provider(active_settings)
    retriever = create_retriever(active_settings)
    provider_registry = build_provider_registry(active_settings)

    cascade = None
    if active_settings.llm_router == "cascade":
        persona, technical = build_layer_configs(active_settings)
        cascade = CascadeResponder(
            persona=persona,
            technical=technical,
            timeout_seconds=active_settings.llm_timeout_seconds,
        )

    # Skills / artifacts (active when an artifact model key is configured).
    skills_dir = active_settings.skills_config_dir or (
        active_settings.repo_root / "configs" / "skills"
    )
    skill_registry = SkillRegistry(skills_dir)
    skill_engine = None
    if active_settings.artifact_api_key:
        skill_engine = SkillEngine(
            provider=OpenAICompatibleProvider(
                base_url=active_settings.artifact_base_url,
                api_key=active_settings.artifact_api_key,
                timeout_seconds=active_settings.llm_timeout_seconds,
            ),
            model=active_settings.artifact_model,
        )

    orchestrator = ChatOrchestrator(
        settings=active_settings,
        provider=provider,
        personality_loader=personality_loader,
        store=store,
        retriever=retriever,
        provider_registry=provider_registry,
        cascade=cascade,
        skill_registry=skill_registry,
        skill_engine=skill_engine,
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
    app.include_router(create_providers_router(active_settings))
    app.include_router(create_chat_router(orchestrator))
    app.include_router(create_memory_router(store, memory_store))
    app.include_router(create_sessions_router(store))
    app.include_router(create_skills_router(skill_registry, skill_engine is not None))
    return app


app = create_app()
