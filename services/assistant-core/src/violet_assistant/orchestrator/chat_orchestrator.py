from __future__ import annotations

from uuid import uuid4

from violet_assistant.config import Settings
from violet_assistant.llm.base import LLMOptions, LLMProvider, Message
from violet_assistant.memory.extractor import extract_memory_candidates
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.personality.loader import PersonalityLoader, build_system_prompt
from violet_assistant.schemas.chat import ChatRequest, ChatResponse


class ChatOrchestrator:
    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider,
        personality_loader: PersonalityLoader,
        store: SQLiteStore,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.personality_loader = personality_loader
        self.store = store

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

        history = self.store.recent_messages(session_id)
        messages = [
            Message(role="system", content=build_system_prompt(profile)),
            *history,
        ]
        llm_response = await self.provider.chat(
            messages,
            LLMOptions(
                model=self.settings.llm_model,
                metadata={
                    "personality_id": profile.id,
                    "personality_name": profile.name,
                },
            ),
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
        )

