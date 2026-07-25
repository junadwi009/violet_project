from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from violet_assistant.config import Settings
from violet_assistant.llm.base import LLMOptions, LLMProvider, LLMResponse, Message
from violet_assistant.memory.extractor import extract_memory_candidates
from violet_assistant.orchestrator.cascade import CascadeResponder
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.personality.loader import PersonalityLoader, build_system_prompt
from violet_assistant.rag.base import Retriever
from violet_assistant.rag.no_op_retriever import NoOpRetriever
from violet_assistant.schemas.chat import Artifact, ChatRequest, ChatResponse
from violet_assistant.skills.generator import SkillEngine
from violet_assistant.skills.registry import SkillRegistry
from violet_assistant.agents.registry import AgentRegistry
from violet_assistant.agents.runner import AgentRunner

if TYPE_CHECKING:
    from violet_assistant.preferences.store import PreferencesStore


class ChatOrchestrator:
    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider,
        personality_loader: PersonalityLoader,
        store: SQLiteStore,
        retriever: Retriever | None = None,
        provider_registry: dict[str, LLMProvider] | None = None,
        cascade: CascadeResponder | None = None,
        skill_registry: SkillRegistry | None = None,
        skill_engine: SkillEngine | None = None,
        agent_registry: AgentRegistry | None = None,
        agent_runner: AgentRunner | None = None,
        preferences: "PreferencesStore | None" = None,
        web_provider: LLMProvider | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.personality_loader = personality_loader
        self.store = store
        self.retriever = retriever or NoOpRetriever()
        self.provider_registry = provider_registry or {}
        self.cascade = cascade
        self.skill_registry = skill_registry
        self.skill_engine = skill_engine
        self.agent_registry = agent_registry
        self.agent_runner = agent_runner
        self.preferences = preferences
        self.web_provider = web_provider

    def _select_provider(self, requested: str | None) -> LLMProvider:
        if requested and requested in self.provider_registry:
            return self.provider_registry[requested]
        return self.provider

    async def chat(self, request: ChatRequest) -> ChatResponse:
        profile = self.personality_loader.load(request.personality_id)
        session_id = request.session_id or str(uuid4())
        title = request.content[:80]
        self.store.ensure_session(session_id, title=title)

        user_message_id = self.store.add_message(
            session_id=session_id,
            role="user",
            content=request.content,
            metadata={
                "input_type": request.input_type,
                "personality_id": profile.id,
                "context": request.context.model_dump(),
            },
        )
        candidates = extract_memory_candidates(request.content, user_message_id)
        self.store.add_memory_candidates(candidates)

        retrieved = await self.retriever.retrieve(request.content)
        context = [chunk.text for chunk in retrieved]

        history = self.store.recent_messages(session_id)
        messages = [
            Message(
                role="system",
                content=build_system_prompt(profile, context=context),
            ),
            *history,
        ]
        prefs = (
            self.preferences.effective(self.settings) if self.preferences else {}
        )
        base_options = LLMOptions(
            model=prefs.get("llm_model", self.settings.llm_model),
            temperature=prefs.get("temperature", self.settings.default_temperature),
            metadata={
                "personality_id": profile.id,
                "personality_name": profile.name,
            },
        )
        artifacts: list[Artifact] = []
        citations: list[str] = []
        agent_used: str | None = None
        is_mock = request.provider == "mock"

        explicit_agent = (
            self.agent_registry.get(request.agent)
            if self.agent_registry is not None
            else None
        )
        explicit_skill = (
            self.skill_registry.get(request.skill_id)
            if (self.skill_registry is not None and request.skill_id)
            else None
        )
        skill = (
            self.skill_registry.detect(request.content)
            if self.skill_registry is not None
            else None
        )

        # Precedence: mock → explicit agent → web-search → explicit skill →
        # auto-detected skill → auto-detected agent → cascade → provider.
        if is_mock:
            llm_response = await self._select_provider(request.provider).chat(
                messages, base_options
            )
        elif explicit_agent is not None and self.agent_runner is not None:
            llm_response = await self.agent_runner.run(explicit_agent, messages)
            agent_used = explicit_agent.id
        elif request.web_search and self.web_provider is not None:
            from violet_assistant.web.search import web_answer

            answer = await web_answer(
                self.web_provider,
                prefs.get("web_search_model", self.settings.web_search_model),
                messages,
            )
            llm_response = LLMResponse(text=answer.text, emotion="focused")
            citations = answer.citations
        elif explicit_skill is not None and self.skill_engine is not None:
            intro, artifact_dicts = await self.skill_engine.generate(
                explicit_skill, request.content
            )
            llm_response = LLMResponse(text=intro, emotion="focused")
            artifacts = [Artifact.model_validate(item) for item in artifact_dicts]
        elif skill is not None and self.skill_engine is not None:
            intro, artifact_dicts = await self.skill_engine.generate(skill, request.content)
            llm_response = LLMResponse(text=intro, emotion="focused")
            artifacts = [Artifact.model_validate(item) for item in artifact_dicts]
        elif (
            self.agent_registry is not None
            and self.agent_runner is not None
            and (detected_agent := self.agent_registry.detect(request.content)) is not None
        ):
            llm_response = await self.agent_runner.run(detected_agent, messages)
            agent_used = detected_agent.id
        elif self.cascade is not None:
            result = await self.cascade.respond(messages, base_options)
            llm_response = LLMResponse(text=result.text, emotion=result.emotion)
        else:
            llm_response = await self._select_provider(request.provider).chat(
                messages, base_options
            )
        assistant_message_id = self.store.add_message(
            session_id=session_id,
            role="assistant",
            content=llm_response.text,
            metadata={"emotion": llm_response.emotion},
        )

        return ChatResponse(
            message_id=assistant_message_id,
            session_id=session_id,
            text=llm_response.text,
            emotion=llm_response.emotion,
            memory_candidates=[
                candidate.to_response() for candidate in candidates
            ],
            tool_requests=[],
            artifacts=artifacts,
            agent=agent_used,
            citations=citations,
        )

