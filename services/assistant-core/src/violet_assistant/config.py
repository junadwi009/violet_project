from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


PACKAGE_FILE = Path(__file__).resolve()
DEFAULT_REPO_ROOT = PACKAGE_FILE.parents[4]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    app_env: str
    app_host: str
    app_port: int
    public_client_url: str
    database_url: str
    llm_provider: str
    llm_base_url: str
    llm_model: str
    llm_timeout_seconds: float
    llm_api_key: str | None
    personality_config_dir: Path
    rag_provider: str
    memory_backend: str
    memory_dir: Path
    memory_auto_save: bool
    memory_require_approval: bool
    log_level: str
    # Multi-layer routing (Phase 2). Defaults keep existing single-provider behavior.
    llm_router: str = "single"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str | None = None
    persona_base_url: str = "https://openrouter.ai/api/v1"
    persona_model: str = "nousresearch/hermes-4-70b"
    persona_api_key: str | None = None
    technical_base_url: str = "https://openrouter.ai/api/v1"
    technical_model: str = "deepseek/deepseek-chat-v3.1"
    technical_api_key: str | None = None
    # Skills / artifacts (Phase 3)
    artifact_base_url: str = "https://openrouter.ai/api/v1"
    artifact_model: str = "qwen/qwen3-coder"
    artifact_api_key: str | None = None
    skills_config_dir: Path | None = None
    # Vision / OCR (Phase 3c)
    vision_base_url: str = "https://openrouter.ai/api/v1"
    vision_model: str = "qwen/qwen3-vl-32b-instruct"
    vision_api_key: str | None = None
    max_upload_mb: int = 15
    # Specialized sub-agents (Phase 3e)
    agents_config_dir: Path | None = None
    agent_base_url: str = "https://openrouter.ai/api/v1"
    agent_api_key: str | None = None
    # Model used for imported SKILL.md agents (they don't specify a model).
    agent_default_model: str = "nousresearch/hermes-4-70b"
    # Web search (Phase 4) — key reuses OpenRouter.
    web_search_base_url: str = "https://openrouter.ai/api/v1"
    web_search_model: str = "deepseek/deepseek-chat-v3.1"
    web_search_api_key: str | None = None
    default_temperature: float = 0.2
    # Knowledge base / RAG (Phase A).
    knowledge_dir: Path | None = None
    knowledge_db: Path | None = None
    embed_provider: str = "mock"
    embed_base_url: str = "http://localhost:11434/v1"
    embed_model: str = "nomic-embed-text"
    embed_api_key: str | None = None
    knowledge_scan_on_startup: bool = True
    knowledge_chunk_size: int = 1000
    knowledge_chunk_overlap: int = 150
    knowledge_sources: str = "local"
    # Google Drive connector (Phase C).
    gdrive_folder_id: str = ""
    gdrive_shared_drive_id: str = ""
    gdrive_token_path: str = ""
    google_oauth_client_secrets: str = ""
    gdrive_export_doc: str = "text/markdown"


def load_settings(repo_root: Path | None = None) -> Settings:
    root = (repo_root or DEFAULT_REPO_ROOT).resolve()
    _load_env_file(root / ".env")

    return Settings(
        repo_root=root,
        app_env=os.getenv("APP_ENV", "local"),
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        public_client_url=os.getenv("PUBLIC_CLIENT_URL", "http://localhost:3000"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/violet.db"),
        llm_provider=os.getenv("LLM_PROVIDER", "mock").strip().lower(),
        llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
        llm_model=os.getenv("LLM_MODEL", "local-model"),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
        llm_api_key=os.getenv("LLM_API_KEY") or None,
        llm_router=os.getenv("LLM_ROUTER", "single").strip().lower(),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
        persona_base_url=os.getenv(
            "PERSONA_BASE_URL",
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ),
        persona_model=os.getenv("PERSONA_MODEL", "nousresearch/hermes-4-70b"),
        persona_api_key=os.getenv("PERSONA_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or None,
        technical_base_url=os.getenv(
            "TECHNICAL_BASE_URL",
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ),
        technical_model=os.getenv(
            "TECHNICAL_MODEL", "deepseek/deepseek-chat-v3.1"
        ),
        technical_api_key=os.getenv("TECHNICAL_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or None,
        artifact_base_url=os.getenv(
            "ARTIFACT_BASE_URL",
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ),
        artifact_model=os.getenv("ARTIFACT_MODEL", "qwen/qwen3-coder"),
        artifact_api_key=os.getenv("ARTIFACT_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or None,
        skills_config_dir=Path(
            os.getenv("SKILLS_CONFIG_DIR", str(root / "configs" / "skills"))
        ),
        vision_base_url=os.getenv(
            "VISION_BASE_URL",
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ),
        vision_model=os.getenv("VISION_MODEL", "qwen/qwen3-vl-32b-instruct"),
        vision_api_key=os.getenv("VISION_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or None,
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "15")),
        agents_config_dir=Path(
            os.getenv("AGENTS_CONFIG_DIR", str(root / "configs" / "agents"))
        ),
        agent_base_url=os.getenv(
            "AGENT_BASE_URL",
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ),
        agent_api_key=os.getenv("AGENT_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or None,
        agent_default_model=os.getenv(
            "AGENT_DEFAULT_MODEL", "nousresearch/hermes-4-70b"
        ),
        web_search_base_url=os.getenv(
            "WEB_SEARCH_BASE_URL",
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ),
        web_search_model=os.getenv(
            "WEB_SEARCH_MODEL",
            os.getenv("TECHNICAL_MODEL", "deepseek/deepseek-chat-v3.1"),
        ),
        web_search_api_key=os.getenv("WEB_SEARCH_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or None,
        default_temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.2")),
        knowledge_dir=Path(os.getenv("KNOWLEDGE_DIR", str(root / "knowledge"))),
        knowledge_db=Path(
            os.getenv("KNOWLEDGE_DB", str(root / "data" / "knowledge.db"))
        ),
        embed_provider=os.getenv("EMBED_PROVIDER", "mock").strip().lower(),
        embed_base_url=os.getenv("EMBED_BASE_URL", "http://localhost:11434/v1"),
        embed_model=os.getenv("EMBED_MODEL", "nomic-embed-text"),
        embed_api_key=os.getenv("EMBED_API_KEY") or None,
        knowledge_scan_on_startup=_env_bool("KNOWLEDGE_SCAN_ON_STARTUP", True),
        knowledge_chunk_size=int(os.getenv("KNOWLEDGE_CHUNK_SIZE", "1000")),
        knowledge_chunk_overlap=int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "150")),
        knowledge_sources=os.getenv("KNOWLEDGE_SOURCES", "local"),
        gdrive_folder_id=os.getenv("GDRIVE_FOLDER_ID", ""),
        gdrive_shared_drive_id=os.getenv("GDRIVE_SHARED_DRIVE_ID", ""),
        gdrive_token_path=os.getenv(
            "GDRIVE_TOKEN_PATH", str(root / "data" / "gdrive_token.json")
        ),
        google_oauth_client_secrets=os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", ""),
        gdrive_export_doc=os.getenv("GDRIVE_EXPORT_DOC", "text/markdown"),
        personality_config_dir=Path(
            os.getenv("PERSONALITY_CONFIG_DIR", str(root / "configs" / "personality"))
        ),
        rag_provider=os.getenv("RAG_PROVIDER", "none").strip().lower(),
        memory_backend=os.getenv("MEMORY_BACKEND", "files").strip().lower(),
        memory_dir=Path(os.getenv("MEMORY_DIR", str(root / "memory"))),
        memory_auto_save=_env_bool("MEMORY_AUTO_SAVE", False),
        memory_require_approval=_env_bool("MEMORY_REQUIRE_APPROVAL", True),
        log_level=os.getenv("LOG_LEVEL", "info"),
    )

