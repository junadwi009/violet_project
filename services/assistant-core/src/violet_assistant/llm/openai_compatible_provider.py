from __future__ import annotations

import asyncio
import json
from typing import Sequence
from urllib import error, request

from violet_assistant.llm.base import (
    LLMOptions,
    LLMResponse,
    Message,
    ProviderHealth,
    ToolCall,
)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 120,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.default_headers = default_headers or {}

    async def chat(
        self, messages: Sequence[Message], options: LLMOptions
    ) -> LLMResponse:
        return await asyncio.to_thread(self._chat_sync, messages, options)

    async def health(self) -> ProviderHealth:
        return await asyncio.to_thread(self._health_sync)

    def _chat_sync(
        self, messages: Sequence[Message], options: LLMOptions
    ) -> LLMResponse:
        payload = {
            "model": options.model,
            "messages": [self._serialize(message) for message in messages],
            "temperature": options.temperature,
            "stream": False,
        }
        if options.tools:
            payload["tools"] = options.tools
        api_response = self._request_json("POST", "/chat/completions", payload)
        message = api_response["choices"][0]["message"]
        text = message.get("content") or ""
        calls = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}  # reported to the model as a tool error by the loop
            if not isinstance(arguments, dict):
                arguments = {}
            calls.append(
                ToolCall(
                    id=raw.get("id", ""),
                    name=function.get("name", ""),
                    arguments=arguments,
                )
            )
        return LLMResponse(text=text, emotion="focused", tool_calls=calls)

    @staticmethod
    def _serialize(message: Message) -> dict:
        data: dict = {"role": message.role, "content": message.content}
        if message.tool_call_id:
            data["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            data["tool_calls"] = message.tool_calls
        return data

    def _health_sync(self) -> ProviderHealth:
        try:
            self._request_json("GET", "/models", None)
        except Exception as exc:  # noqa: BLE001 - health should report failures.
            return ProviderHealth(
                provider=self.name,
                status="unhealthy",
                detail=str(exc),
            )
        return ProviderHealth(provider=self.name, status="ok")

    def _request_json(
        self, method: str, path: str, payload: dict | None
    ) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", **self.default_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        api_request = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(api_request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Provider returned HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Provider is unreachable: {exc.reason}") from exc

