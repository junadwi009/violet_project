from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Message:
    role: str                                    # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: str | None = None              # set when role == "tool"
    tool_calls: list[dict] | None = None         # set on an assistant turn that called tools


@dataclass(frozen=True)
class LLMOptions:
    model: str
    temperature: float = 0.3
    metadata: dict[str, str] = field(default_factory=dict)
    tools: list[dict] | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    emotion: str = "neutral"
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    status: str
    detail: str | None = None


class LLMProvider(Protocol):
    name: str

    async def chat(
        self, messages: Sequence[Message], options: LLMOptions
    ) -> LLMResponse:
        """Return a complete assistant response for the supplied messages."""

    async def health(self) -> ProviderHealth:
        """Return provider health without requiring a paid API by default."""

