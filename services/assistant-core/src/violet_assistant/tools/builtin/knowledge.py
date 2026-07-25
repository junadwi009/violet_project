from __future__ import annotations

from violet_assistant.tools.base import ToolResult


class KnowledgeSearchTool:
    name = "knowledge_search"
    description = (
        "Search the user's local knowledge base (their own indexed documents) "
        "and return the most relevant passages with their source filenames."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for."},
            "k": {
                "type": "integer",
                "description": "How many passages (default 4).",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
    }
    risk = "low"
    required_flags: tuple[str, ...] = ()

    def __init__(self, retriever) -> None:
        self.retriever = retriever

    async def run(self, args: dict) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(text="query is required", error="missing query")
        k = int(args.get("k") or 4)
        chunks = await self.retriever.retrieve(query, k=k)
        if not chunks:
            return ToolResult(text="No matching passages in the knowledge base.")
        parts, citations = [], []
        for chunk in chunks:
            parts.append(f"[{chunk.source}] {chunk.text}")
            if chunk.source and chunk.source not in citations:
                citations.append(chunk.source)
        # Local documents are the user's own, so not flagged untrusted.
        return ToolResult(text="\n\n".join(parts), citations=citations)
