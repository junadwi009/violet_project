from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Sequence

from violet_assistant.llm.base import LLMOptions, LLMProvider, Message


@dataclass(frozen=True)
class WebAnswer:
    text: str
    citations: list[str] = field(default_factory=list)


def parse_web_response(raw: dict[str, Any]) -> WebAnswer:
    """Extract answer text + OpenRouter url_citation annotations from a raw response."""
    message = raw["choices"][0]["message"]
    text = (message.get("content") or "").strip()
    citations: list[str] = []
    for note in message.get("annotations") or []:
        if note.get("type") == "url_citation":
            url = (note.get("url_citation") or {}).get("url")
            if url and url not in citations:
                citations.append(url)
    return WebAnswer(text=text, citations=citations)


async def web_answer(
    provider: LLMProvider, model: str, messages: Sequence[Message]
) -> WebAnswer:
    """Ask an OpenRouter-backed provider with web search on (model + ':online').

    Calls the provider's raw ``_request_json`` so we can read the citation
    annotations that ``LLMResponse`` drops. This is deliberate coupling to
    ``OpenAICompatibleProvider`` and is the only place that reaches into it.
    """
    online_model = model if model.endswith(":online") else f"{model}:online"
    payload = {
        "model": online_model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": LLMOptions(model=online_model).temperature,
        "stream": False,
    }
    raw = await asyncio.to_thread(
        provider._request_json, "POST", "/chat/completions", payload  # noqa: SLF001
    )
    return parse_web_response(raw)
