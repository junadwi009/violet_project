from __future__ import annotations

from typing import Sequence

from violet_assistant.agents.schema import Agent
from violet_assistant.llm.base import LLMOptions, LLMProvider, LLMResponse, Message
from violet_assistant.llm.openai_compatible_provider import OpenAICompatibleProvider


class AgentRunner:
    """Runs a specialized agent: its own model + system prompt over the conversation."""

    def __init__(
        self,
        default_base_url: str,
        api_key: str | None,
        timeout_seconds: float = 120,
        provider_factory=None,
    ) -> None:
        self.default_base_url = default_base_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._make = provider_factory or self._default_provider_factory

    def _default_provider_factory(self, base_url: str) -> LLMProvider:
        return OpenAICompatibleProvider(
            base_url=base_url,
            api_key=self.api_key,
            timeout_seconds=self.timeout_seconds,
            default_headers={
                "HTTP-Referer": "https://localhost/violet",
                "X-Title": "Violet Assistant",
            },
        )

    async def run(self, agent: Agent, history: Sequence[Message]) -> LLMResponse:
        provider = self._make(agent.base_url or self.default_base_url)
        # Replace the base system prompt with the agent's specialized instructions; keep the
        # conversation turns so the agent has context.
        turns = [m for m in history if m.role != "system"]
        messages = [Message(role="system", content=agent.system_prompt), *turns]
        return await provider.chat(messages, LLMOptions(model=agent.model, temperature=0.4))
