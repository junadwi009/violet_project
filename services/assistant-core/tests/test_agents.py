from __future__ import annotations

import asyncio
import json
from pathlib import Path

from violet_assistant.agents.registry import AgentRegistry
from violet_assistant.agents.runner import AgentRunner
from violet_assistant.agents.schema import Agent
from violet_assistant.llm.base import LLMOptions, LLMResponse, Message


def _write(tmp_path: Path, *agents: dict) -> Path:
    d = tmp_path / "agents"
    d.mkdir(exist_ok=True)
    for a in agents:
        (d / f"{a['id']}.json").write_text(json.dumps(a), encoding="utf-8")
    return d


def test_registry_get_and_detect(tmp_path) -> None:
    d = _write(
        tmp_path,
        {"id": "researcher", "name": "Researcher", "model": "m1", "system_prompt": "p", "triggers": ["research", "deep dive"]},
        {"id": "coder", "name": "Coder", "model": "m2", "system_prompt": "p", "triggers": ["write code", "debug this"]},
    )
    registry = AgentRegistry(d)
    assert registry.get("coder").id == "coder"
    assert registry.get(None) is None
    assert registry.get("nope") is None
    assert registry.detect("please research the market").id == "researcher"
    assert registry.detect("write code for a parser").id == "coder"
    assert registry.detect("hello there") is None


class RecordingProvider:
    def __init__(self) -> None:
        self.model = None
        self.system = None

    async def chat(self, messages, options: LLMOptions) -> LLMResponse:
        self.model = options.model
        self.system = messages[0].content if messages else ""
        return LLMResponse(text="agent answer", emotion="focused")

    async def health(self):  # pragma: no cover
        raise NotImplementedError


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "001_init.sql"


def _orchestrator(tmp_path):
    from violet_assistant.config import Settings
    from violet_assistant.llm.mock_provider import MockLLMProvider
    from violet_assistant.orchestrator.chat_orchestrator import ChatOrchestrator
    from violet_assistant.persistence.sqlite_store import SQLiteStore
    from violet_assistant.personality.loader import PersonalityLoader
    from violet_assistant.skills.registry import SkillRegistry

    pdir = tmp_path / "personality"
    pdir.mkdir()
    (pdir / "violet.default.json").write_text(
        json.dumps({"id": "violet.default", "name": "Violet"}), encoding="utf-8"
    )
    agents_dir = _write(
        tmp_path,
        {"id": "coder", "name": "Coder", "model": "coder-model", "system_prompt": "p", "triggers": ["write code"]},
    )
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "chart.json").write_text(
        json.dumps({"id": "chart", "name": "Chart", "kind": "chartjs", "triggers": ["chart"], "prompt": "p"}),
        encoding="utf-8",
    )

    settings = Settings(
        repo_root=PROJECT_ROOT, app_env="test", app_host="127.0.0.1", app_port=8000,
        public_client_url="http://localhost:3000",
        database_url=f"sqlite:///{tmp_path / 'v.db'}", llm_provider="mock",
        llm_base_url="http://x", llm_model="m", llm_timeout_seconds=1, llm_api_key=None,
        personality_config_dir=pdir, rag_provider="none", memory_backend="sqlite",
        memory_dir=tmp_path / "mem", memory_auto_save=False, memory_require_approval=True,
        log_level="debug",
    )
    store = SQLiteStore.from_database_url(settings.database_url, base_dir=PROJECT_ROOT, migration_path=MIGRATION_PATH)
    store.initialize()

    class FakeSkillEngine:
        async def generate(self, skill, content):
            return "SKILL", [{"id": "a1", "kind": "chartjs", "title": "", "spec": {"type": "bar"},
                              "html": None, "file_base64": None, "filename": None, "mime": None}]

    class FakeAgentRunner:
        async def run(self, agent, messages):
            return LLMResponse(text=f"AGENT:{agent.id}", emotion="focused")

    return ChatOrchestrator(
        settings=settings, provider=MockLLMProvider(),
        personality_loader=PersonalityLoader(pdir), store=store,
        skill_registry=SkillRegistry(skills_dir), skill_engine=FakeSkillEngine(),
        agent_registry=AgentRegistry(agents_dir), agent_runner=FakeAgentRunner(),
    )


def test_precedence_explicit_agent_beats_skill(tmp_path) -> None:
    from violet_assistant.schemas.chat import ChatRequest

    orch = _orchestrator(tmp_path)
    # explicit agent + a chart request → agent wins, no artifact
    r = asyncio.run(orch.chat(ChatRequest(content="make a chart", agent="coder", provider="openai_compatible")))
    assert r.agent == "coder"
    assert r.text == "AGENT:coder"
    assert r.artifacts == []


def test_precedence_skill_beats_detected_agent(tmp_path) -> None:
    from violet_assistant.schemas.chat import ChatRequest

    orch = _orchestrator(tmp_path)
    # "chart" matches a skill; no explicit agent → skill wins
    r = asyncio.run(orch.chat(ChatRequest(content="make a chart", provider="openai_compatible")))
    assert r.agent is None
    assert len(r.artifacts) == 1


def test_precedence_detected_agent_when_no_skill(tmp_path) -> None:
    from violet_assistant.schemas.chat import ChatRequest

    orch = _orchestrator(tmp_path)
    r = asyncio.run(orch.chat(ChatRequest(content="write code for a parser", provider="openai_compatible")))
    assert r.agent == "coder"


def test_mock_bypasses_agents_and_skills(tmp_path) -> None:
    from violet_assistant.schemas.chat import ChatRequest

    orch = _orchestrator(tmp_path)
    r = asyncio.run(orch.chat(ChatRequest(content="make a chart", agent="coder", provider="mock")))
    assert r.agent is None
    assert r.artifacts == []
    assert r.text.startswith("Violet mock response")


def test_runner_uses_agent_model_and_prompt() -> None:
    provider = RecordingProvider()
    runner = AgentRunner(
        default_base_url="http://x",
        api_key=None,
        provider_factory=lambda base_url: provider,
    )
    agent = Agent(id="coder", name="Coder", model="qwen/qwen3-coder", system_prompt="You are the Coder.")
    history = [
        Message(role="system", content="base persona prompt"),
        Message(role="user", content="write a fizzbuzz"),
    ]
    result = asyncio.run(runner.run(agent, history))

    assert result.text == "agent answer"
    assert provider.model == "qwen/qwen3-coder"
    assert provider.system == "You are the Coder."  # agent prompt replaces the base system prompt
