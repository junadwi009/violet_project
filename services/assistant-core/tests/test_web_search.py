from __future__ import annotations

from violet_assistant.web.search import WebAnswer, parse_web_response


def test_parse_web_response_extracts_text_and_citations():
    raw = {
        "choices": [
            {
                "message": {
                    "content": "Answer.",
                    "annotations": [
                        {"type": "url_citation", "url_citation": {"url": "https://a.example"}},
                        {"type": "url_citation", "url_citation": {"url": "https://b.example"}},
                    ],
                }
            }
        ]
    }
    result = parse_web_response(raw)
    assert isinstance(result, WebAnswer)
    assert result.text == "Answer."
    assert result.citations == ["https://a.example", "https://b.example"]


def test_parse_web_response_without_annotations():
    raw = {"choices": [{"message": {"content": "Hi"}}]}
    assert parse_web_response(raw) == WebAnswer(text="Hi", citations=[])


def test_parse_web_response_dedupes_citations():
    raw = {
        "choices": [
            {
                "message": {
                    "content": "x",
                    "annotations": [
                        {"type": "url_citation", "url_citation": {"url": "https://a"}},
                        {"type": "url_citation", "url_citation": {"url": "https://a"}},
                        {"type": "other", "url_citation": {"url": "https://ignored"}},
                    ],
                }
            }
        ]
    }
    assert parse_web_response(raw).citations == ["https://a"]
