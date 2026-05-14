from __future__ import annotations

import asyncio

from violet_assistant.llm.base import LLMOptions, Message
from violet_assistant.llm.mock_provider import MockLLMProvider


def test_mock_provider_returns_deterministic_response() -> None:
    provider = MockLLMProvider()

    response = asyncio.run(
        provider.chat(
            [Message(role="user", content="Hello Violet")],
            LLMOptions(
                model="mock-model",
                metadata={"personality_name": "Violet"},
            ),
        )
    )

    assert response.emotion == "focused"
    assert "Hello Violet" in response.text
    assert "safe local mock mode" in response.text


def test_mock_provider_health_is_ok() -> None:
    provider = MockLLMProvider()

    health = asyncio.run(provider.health())

    assert health.provider == "mock"
    assert health.status == "ok"

