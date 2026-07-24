from __future__ import annotations

import asyncio

from violet_assistant.llm.base import LLMOptions, LLMResponse, Message
from violet_assistant.orchestrator.cascade import CascadeResponder, LayerConfig


class ScriptedProvider:
    """Returns queued responses and records the (model, messages) it was called with."""

    def __init__(self, name: str, replies: list[str]) -> None:
        self.name = name
        self._replies = list(replies)
        self.calls: list[tuple[str, list[Message]]] = []

    async def chat(self, messages, options: LLMOptions) -> LLMResponse:
        self.calls.append((options.model, list(messages)))
        return LLMResponse(text=self._replies.pop(0), emotion="focused")

    async def health(self):  # pragma: no cover
        raise NotImplementedError


def _cascade(persona_replies, technical_replies):
    persona = LayerConfig("persona", "http://p", "persona-model", None)
    technical = LayerConfig("technical", "http://t", "technical-model", None)
    persona_provider = ScriptedProvider("persona", persona_replies)
    technical_provider = ScriptedProvider("technical", technical_replies)
    providers = {"persona": persona_provider, "technical": technical_provider}
    responder = CascadeResponder(
        persona=persona,
        technical=technical,
        provider_factory=lambda layer: providers[layer.name],
    )
    return responder, persona_provider, technical_provider


def test_no_delegation_returns_persona_reply() -> None:
    responder, persona_p, technical_p = _cascade(
        persona_replies=["Hello, I'm Violet."], technical_replies=[]
    )
    messages = [Message(role="system", content="You are Violet."), Message(role="user", content="hi")]

    result = asyncio.run(responder.respond(messages, LLMOptions(model="ignored")))

    assert result.text == "Hello, I'm Violet."
    assert result.delegated is False
    assert len(persona_p.calls) == 1
    assert len(technical_p.calls) == 0
    # delegation instruction was appended to the system message
    assert "DELEGATE:" in persona_p.calls[0][1][0].content


def test_delegation_calls_technical_then_persona_compose() -> None:
    responder, persona_p, technical_p = _cascade(
        persona_replies=["DELEGATE: compute 17 * 23", "It's 391 — done."],
        technical_replies=["17 * 23 = 391"],
    )
    messages = [
        Message(role="system", content="You are Violet."),
        Message(role="user", content="what is 17 times 23?"),
    ]

    result = asyncio.run(responder.respond(messages, LLMOptions(model="ignored")))

    assert result.delegated is True
    assert result.text == "It's 391 — done."
    assert len(persona_p.calls) == 2  # initial + compose
    assert len(technical_p.calls) == 1
    # technical layer received the extracted subtask
    assert technical_p.calls[0][1][-1].content == "compute 17 * 23"
    assert result.models_used == ["persona-model", "technical-model", "persona-model"]


def test_delegation_is_capped_at_one() -> None:
    # Even if the compose step were to emit another DELEGATE, we do not recurse.
    responder, persona_p, technical_p = _cascade(
        persona_replies=["DELEGATE: do a thing", "DELEGATE: do another thing"],
        technical_replies=["result-1"],
    )
    messages = [Message(role="system", content="sys"), Message(role="user", content="go")]

    result = asyncio.run(responder.respond(messages, LLMOptions(model="ignored")))

    assert len(technical_p.calls) == 1  # only one delegation round
    assert result.text == "DELEGATE: do another thing"  # returned verbatim, not re-delegated
