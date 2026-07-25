from __future__ import annotations

import asyncio

from violet_assistant.tools.base import ToolResult
from violet_assistant.web.fetch import fetch_url


class WebSearchTool:
    name = "web_search"
    description = "Search the public web and return an answer with source URLs."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The search query."}},
        "required": ["query"],
    }
    risk = "medium"
    required_flags: tuple[str, ...] = ()

    def __init__(self, provider, model: str) -> None:
        self.provider = provider
        self.model = model

    async def run(self, args: dict) -> ToolResult:
        from violet_assistant.llm.base import Message
        from violet_assistant.web.search import web_answer

        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(text="query is required", error="missing query")
        try:
            answer = await web_answer(
                self.provider, self.model, [Message(role="user", content=query)]
            )
        except Exception as exc:  # noqa: BLE001 — report, let the model recover
            return ToolResult(text=f"Web search failed: {exc}", error=str(exc))
        return ToolResult(text=answer.text, citations=answer.citations, untrusted=True)


class FetchUrlTool:
    name = "fetch_url"
    description = "Fetch a specific public web page and return its readable text."
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "An http(s) URL."}},
        "required": ["url"],
    }
    risk = "medium"
    required_flags: tuple[str, ...] = ()

    async def run(self, args: dict) -> ToolResult:
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(text="url is required", error="missing url")
        try:
            result = await asyncio.to_thread(fetch_url, url)
        except ValueError as exc:  # blocked host, bad scheme, unreachable
            return ToolResult(text=f"Could not fetch: {exc}", error=str(exc))
        body = f"{result.title}\n\n{result.text}" if result.title else result.text
        return ToolResult(text=body, citations=[result.url], untrusted=True)
