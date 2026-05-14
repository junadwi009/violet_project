from __future__ import annotations

from typing import Sequence

from violet_assistant.llm.base import LLMOptions, LLMResponse, Message, ProviderHealth


class MockLLMProvider:
    name = "mock"

    async def chat(
        self, messages: Sequence[Message], options: LLMOptions
    ) -> LLMResponse:
        user_message = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )
        persona = options.metadata.get("personality_name", "Violet")
        text = (
            f"{persona} mock response: I heard you say, \"{user_message}\". "
            "I am running in safe local mock mode, so no external model or paid API was used."
        )
        return LLMResponse(text=text, emotion="focused")

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status="ok",
            detail="Deterministic local mock provider is ready.",
        )

