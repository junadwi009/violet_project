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
from violet_assistant.routes.fetch import create_fetch_router
from violet_assistant.routes.knowledge import create_knowledge_router
from violet_assistant.routes.settings import create_settings_router
from violet_assistant.knowledge.indexer import KnowledgeIndexer
from violet_assistant.vector.embeddings.factory import create_embedder
from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore
from violet_assistant.routes.skills import create_skills_router
from violet_assistant.routes.upload import create_upload_router
from violet_assistant.preferences.store import PreferencesStore
from violet_assistant.ingestion.ocr import VisionOCR
from violet_assistant.llm.openai_compatible_provider import OpenAICompatibleProvider
from violet_assistant.skills.generator import SkillEngine
from violet_assistant.skills.registry import SkillRegistry
from violet_assistant.routes.agents import create_agents_router
from violet_assistant.routes.skill_admin import create_skill_admin_router
from violet_assistant.agents.registry import AgentRegistry
from violet_assistant.agents.runner import AgentRunner


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

    preferences = PreferencesStore(active_settings.repo_root / "data" / "preferences.json")

    personality_loader = PersonalityLoader(active_settings.personality_config_dir)
    provider = create_llm_provider(active_settings)
    retriever = create_retriever(active_settings)
    provider_registry = build_provider_registry(active_settings)

    # Knowledge base (active when RAG_PROVIDER=vector).
    knowledge_indexer = None
    knowledge_store = None
    knowledge_model = "none"
    knowledge_sources: list = []
    knowledge_scheduler = None
    if active_settings.rag_provider.strip().lower() == "vector":
        from violet_assistant.knowledge.sources.local_folder import LocalFolderSource

        knowledge_store = SqliteVectorStore(active_settings.knowledge_db)
        knowledge_store.initialize()
        knowledge_embedder = create_embedder(active_settings)
        knowledge_model = knowledge_embedder.name
        enabled = {
            s.strip() for s in active_settings.knowledge_sources.split(",") if s.strip()
        }
        if "local" in enabled:
            knowledge_sources.append(LocalFolderSource(active_settings.knowledge_dir))
        if (
            "gdrive" in enabled
            and active_settings.gdrive_folder_id
            and active_settings.google_oauth_client_secrets
        ):
            from violet_assistant.knowledge.sources.google_drive import GoogleDriveSource

            knowledge_sources.append(GoogleDriveSource(active_settings))
        knowledge_indexer = KnowledgeIndexer(
            embedder=knowledge_embedder,
            store=knowledge_store,
            sources=knowledge_sources,
            chunk_size=active_settings.knowledge_chunk_size,
            chunk_overlap=active_settings.knowledge_chunk_overlap,
        )
        if active_settings.knowledge_scan_on_startup:
            import asyncio

            try:
                asyncio.new_event_loop().run_until_complete(
                    knowledge_indexer.reindex()
                )
            except Exception:  # noqa: BLE001 — startup scan is best-effort
                pass
        from violet_assistant.knowledge.auto_sync import AutoSyncScheduler

        knowledge_scheduler = AutoSyncScheduler(
            knowledge_indexer, preferences, active_settings
        )

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

    # Web search (active when an OpenRouter-compatible key is configured).
    web_provider = None
    if active_settings.web_search_api_key:
        web_provider = OpenAICompatibleProvider(
            base_url=active_settings.web_search_base_url,
            api_key=active_settings.web_search_api_key,
            timeout_seconds=active_settings.llm_timeout_seconds,
            default_headers={
                "HTTP-Referer": "https://localhost/violet",
                "X-Title": "Violet",
            },
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
        preferences=preferences,
        web_provider=web_provider,
    )

    agents_dir = active_settings.agents_config_dir or (
        active_settings.repo_root / "configs" / "agents"
    )
    agent_registry = AgentRegistry(
        agents_dir, default_model=active_settings.agent_default_model
    )
    agent_runner = None
    if active_settings.agent_api_key:
        agent_runner = AgentRunner(
            default_base_url=active_settings.agent_base_url,
            api_key=active_settings.agent_api_key,
            timeout_seconds=active_settings.llm_timeout_seconds,
        )
    orchestrator.agent_registry = agent_registry
    orchestrator.agent_runner = agent_runner

    vision = None
    if active_settings.vision_api_key:
        vision = VisionOCR(
            base_url=active_settings.vision_base_url,
            api_key=active_settings.vision_api_key,
            model=active_settings.vision_model,
            timeout_seconds=active_settings.llm_timeout_seconds,
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
    app.include_router(create_settings_router(preferences, active_settings))
    app.include_router(create_fetch_router())
    app.include_router(
        create_knowledge_router(
            knowledge_indexer,
            knowledge_store,
            str(active_settings.knowledge_dir),
            knowledge_model,
            knowledge_sources,
            next((s for s in knowledge_sources if s.name == "gdrive"), None),
            active_settings,
            knowledge_scheduler,
        )
    )
    app.include_router(create_skills_router(skill_registry, skill_engine is not None))
    app.include_router(create_agents_router(agent_registry, agent_runner is not None))
    app.include_router(create_upload_router(vision, active_settings.max_upload_mb))

    admin_provider = None
    if active_settings.agent_api_key:
        admin_provider = OpenAICompatibleProvider(
            base_url=active_settings.agent_base_url,
            api_key=active_settings.agent_api_key,
            timeout_seconds=active_settings.llm_timeout_seconds,
            default_headers={"HTTP-Referer": "https://localhost/violet", "X-Title": "Violet"},
        )
    app.include_router(
        create_skill_admin_router(
            skill_registry,
            agent_registry,
            admin_provider,
            active_settings.agent_default_model,
            imported_dir=agents_dir / "imported",
        )
    )

    @app.on_event("startup")
    async def _start_autosync() -> None:  # pragma: no cover — server lifecycle
        if knowledge_scheduler is not None:
            await knowledge_scheduler.start()

    @app.on_event("shutdown")
    async def _stop_autosync() -> None:  # pragma: no cover — server lifecycle
        if knowledge_scheduler is not None:
            await knowledge_scheduler.stop()

    return app


app = create_app()
