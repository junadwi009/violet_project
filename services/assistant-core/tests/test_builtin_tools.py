from __future__ import annotations

import pytest

from violet_assistant.config import load_settings
from violet_assistant.rag.base import Chunk
from violet_assistant.tools.builtin.artifact import CreateArtifactTool
from violet_assistant.tools.builtin.knowledge import KnowledgeSearchTool
from violet_assistant.tools.builtin.web import FetchUrlTool
from violet_assistant.tools.registry import create_tool_registry


class _FakeRetriever:
    name = "fake"

    async def retrieve(self, query, k=4):
        return [Chunk(text=f"chunk about {query}", source="notes.md", score=0.9)]


@pytest.mark.asyncio
async def test_knowledge_tool_returns_text_and_citations():
    tool = KnowledgeSearchTool(_FakeRetriever())
    result = await tool.run({"query": "violet"})
    assert "chunk about violet" in result.text
    assert result.citations == ["notes.md"]
    assert result.untrusted is False
    assert tool.risk == "low"


@pytest.mark.asyncio
async def test_knowledge_tool_handles_no_hits():
    class _Empty:
        name = "empty"

        async def retrieve(self, query, k=4):
            return []

    result = await KnowledgeSearchTool(_Empty()).run({"query": "x"})
    assert "no matching" in result.text.lower()
    assert result.citations == []


@pytest.mark.asyncio
async def test_fetch_url_tool_is_untrusted_and_blocks_internal_hosts():
    tool = FetchUrlTool()
    assert tool.risk == "medium"
    result = await tool.run({"url": "http://127.0.0.1:8000/secret"})
    assert result.error is not None
    assert "not allowed" in result.text.lower() or "not allowed" in result.error.lower()


@pytest.mark.asyncio
async def test_create_artifact_tool_returns_artifacts():
    from violet_assistant.skills.schema import Skill

    class _Registry:
        def get(self, skill_id):
            return Skill(
                id="chart", name="Chart", kind="chartjs", triggers=["chart"],
                prompt="p", display="inline",
            )

    class _Engine:
        async def generate(self, skill, content):
            return "here it is", [
                {
                    "id": "a1", "kind": "chartjs", "title": "Chart", "display": "inline",
                    "spec": {"type": "bar"}, "html": None, "file_base64": None,
                    "filename": None, "mime": None,
                }
            ]

    tool = CreateArtifactTool(_Registry(), _Engine())
    result = await tool.run({"skill_id": "chart", "request": "plot sales"})
    assert len(result.artifacts) == 1
    assert result.artifacts[0]["kind"] == "chartjs"
    assert result.untrusted is False


@pytest.mark.asyncio
async def test_create_artifact_tool_rejects_unknown_skill():
    class _Registry:
        def get(self, skill_id):
            return None

    result = await CreateArtifactTool(_Registry(), object()).run(
        {"skill_id": "nope", "request": "x"}
    )
    assert result.error is not None


def test_registry_factory_only_builds_available_tools(tmp_path):
    settings = load_settings(tmp_path)
    reg = create_tool_registry(settings)
    assert [t.name for t in reg.enabled()] == ["fetch_url"]

    reg2 = create_tool_registry(settings, retriever=_FakeRetriever())
    assert set(t.name for t in reg2.enabled()) == {"fetch_url", "knowledge_search"}
