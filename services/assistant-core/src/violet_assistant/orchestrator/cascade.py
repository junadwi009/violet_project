from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from violet_assistant.config import Settings
from violet_assistant.llm.base import LLMOptions, LLMProvider, LLMResponse, Message
from violet_assistant.llm.openai_compatible_provider import OpenAICompatibleProvider


DELEGATE_MARKER = "DELEGATE:"

_DELEGATION_INSTRUCTION = (
    "\n\nYou are the front layer. Answer directly in character whenever you can. "
    "If — and only if — the request needs heavy calculation, code, or rigorous technical "
    f"reasoning, reply with exactly one line: `{DELEGATE_MARKER} <a focused, self-contained "
    "description of the technical sub-task>` and nothing else. Do not delegate ordinary "
    "conversation."
)

_TECHNICAL_SYSTEM = (
    "You are a precise technical engine. Solve the given sub-task exactly and concisely. "
    "Show the result clearly. No persona, no pleasantries."
)


@dataclass(frozen=True)
class LayerConfig:
    name: str
    base_url: str
    model: str
    api_key: str | None


@dataclass
class CascadeResult:
    text: str
    emotion: str = "focused"
    delegated: bool = False
    models_used: list[str] = field(default_factory=list)


def build_layer_configs(settings: Settings) -> tuple[LayerConfig, LayerConfig]:
    persona = LayerConfig(
        name="persona",
        base_url=settings.persona_base_url,
        model=settings.persona_model,
        api_key=settings.persona_api_key,
    )
    technical = LayerConfig(
        name="technical",
        base_url=settings.technical_base_url,
        model=settings.technical_model,
        api_key=settings.technical_api_key,
    )
    return persona, technical


def _openrouter_headers() -> dict[str, str]:
    # Optional attribution headers OpenRouter uses for app rankings; harmless elsewhere.
    return {"HTTP-Referer": "https://localhost/violet", "X-Title": "Violet Assistant"}


class CascadeResponder:
    """Persona-first cascade with single-step delegation to a technical layer.

    Most turns are one persona call. When the persona layer emits ``DELEGATE: <subtask>`` the
    technical layer runs once and the persona layer composes the final in-character answer.
    Both layers are ``LLMProvider``s (OpenAI-compatible); each may point at a different endpoint
    so the persona layer can later run on a local host while the technical layer uses the API.
    """

    def __init__(
        self,
        persona: LayerConfig,
        technical: LayerConfig,
        timeout_seconds: float = 120,
        provider_factory=None,
    ) -> None:
        self.persona = persona
        self.technical = technical
        self._make = provider_factory or self._default_provider_factory
        self.timeout_seconds = timeout_seconds
        self._persona_provider = self._make(persona)
        self._technical_provider = self._make(technical)

    def _default_provider_factory(self, layer: LayerConfig) -> LLMProvider:
        return OpenAICompatibleProvider(
            base_url=layer.base_url,
            api_key=layer.api_key,
            timeout_seconds=self.timeout_seconds,
            default_headers=_openrouter_headers(),
        )

    async def respond(
        self, messages: Sequence[Message], base_options: LLMOptions
    ) -> CascadeResult:
        persona_messages = self._with_delegation_instruction(messages)
        first = await self._persona_provider.chat(
            persona_messages,
            LLMOptions(model=self.persona.model, temperature=base_options.temperature),
        )

        subtask = self._delegation_subtask(first.text)
        if subtask is None:
            return CascadeResult(
                text=first.text,
                emotion=first.emotion,
                delegated=False,
                models_used=[self.persona.model],
            )

        technical = await self._technical_provider.chat(
            [
                Message(role="system", content=_TECHNICAL_SYSTEM),
                Message(role="user", content=subtask),
            ],
            LLMOptions(model=self.technical.model, temperature=0.0),
        )

        composed = await self._persona_provider.chat(
            [
                *messages,
                Message(
                    role="system",
                    content=(
                        "The technical engine returned the result below. Use it to answer the "
                        "user's last message in character. Do not mention delegation.\n\n"
                        f"Technical result:\n{technical.text}"
                    ),
                ),
            ],
            LLMOptions(model=self.persona.model, temperature=base_options.temperature),
        )
        return CascadeResult(
            text=composed.text,
            emotion=composed.emotion,
            delegated=True,
            models_used=[self.persona.model, self.technical.model, self.persona.model],
        )

    @staticmethod
    def _with_delegation_instruction(messages: Sequence[Message]) -> list[Message]:
        result = list(messages)
        for index, message in enumerate(result):
            if message.role == "system":
                result[index] = Message(
                    role="system",
                    content=message.content + _DELEGATION_INSTRUCTION,
                )
                return result
        result.insert(
            0, Message(role="system", content=_DELEGATION_INSTRUCTION.strip())
        )
        return result

    @staticmethod
    def _delegation_subtask(text: str) -> str | None:
        stripped = text.strip()
        if not stripped.startswith(DELEGATE_MARKER):
            return None
        subtask = stripped[len(DELEGATE_MARKER):].strip()
        return subtask or None
