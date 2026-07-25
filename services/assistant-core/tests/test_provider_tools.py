from __future__ import annotations

import json

from violet_assistant.llm.base import LLMOptions, Message
from violet_assistant.llm.openai_compatible_provider import OpenAICompatibleProvider


def _provider_capturing(payload_box, response):
    p = OpenAICompatibleProvider(base_url="http://x/v1", api_key="k")

    def _fake_request_json(method, path, payload):
        payload_box.append(payload)
        return response

    p._request_json = _fake_request_json  # noqa: SLF001 — test seam
    return p


def test_tools_are_sent_and_tool_calls_parsed():
    box = []
    response = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "knowledge_search",
                                "arguments": json.dumps({"query": "violet"}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    provider = _provider_capturing(box, response)
    tools = [
        {
            "type": "function",
            "function": {"name": "knowledge_search", "description": "d", "parameters": {}},
        }
    ]
    result = provider._chat_sync(
        [Message(role="user", content="hi")], LLMOptions(model="m", tools=tools)
    )
    assert box[0]["tools"] == tools
    assert result.text == ""
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_1"
    assert result.tool_calls[0].name == "knowledge_search"
    assert result.tool_calls[0].arguments == {"query": "violet"}


def test_malformed_arguments_become_empty_dict():
    box = []
    response = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c",
                            "type": "function",
                            "function": {"name": "t", "arguments": "{not json"},
                        }
                    ],
                }
            }
        ]
    }
    provider = _provider_capturing(box, response)
    result = provider._chat_sync(
        [Message(role="user", content="x")], LLMOptions(model="m")
    )
    assert result.tool_calls[0].arguments == {}


def test_tool_role_messages_are_serialised():
    box = []
    provider = _provider_capturing(box, {"choices": [{"message": {"content": "ok"}}]})
    provider._chat_sync(
        [
            Message(role="user", content="q"),
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "t", "arguments": "{}"},
                    }
                ],
            ),
            Message(role="tool", content="result text", tool_call_id="c1"),
        ],
        LLMOptions(model="m"),
    )
    sent = box[0]["messages"]
    assert sent[1]["tool_calls"][0]["id"] == "c1"
    assert sent[2] == {"role": "tool", "content": "result text", "tool_call_id": "c1"}


def test_no_tools_key_when_not_requested():
    box = []
    provider = _provider_capturing(box, {"choices": [{"message": {"content": "ok"}}]})
    provider._chat_sync([Message(role="user", content="x")], LLMOptions(model="m"))
    assert "tools" not in box[0]
