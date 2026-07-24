from __future__ import annotations

from violet_assistant.documents.render import render_docx, render_pptx
from violet_assistant.skills.generator import _render_file_artifacts, parse_artifacts


def test_render_docx_produces_valid_office_zip() -> None:
    data = render_docx(
        {
            "title": "Q3 Report",
            "subtitle": "Draft",
            "sections": [
                {"heading": "Summary", "paragraphs": ["All good."], "bullets": ["Up 10%"]},
                {"heading": "Data", "table": {"headers": ["M", "Rev"], "rows": [["Jul", "100"]]}},
            ],
        }
    )
    assert data[:2] == b"PK"  # OOXML is a zip
    assert len(data) > 1000


def test_render_pptx_produces_valid_office_zip() -> None:
    data = render_pptx(
        {
            "title": "Kickoff",
            "slides": [
                {"title": "Agenda", "bullets": ["Intro", "Plan"], "notes": "hi"},
                {"title": "Next", "bullets": ["Ship"]},
            ],
        }
    )
    assert data[:2] == b"PK"
    assert len(data) > 1000


def test_render_handles_sparse_spec() -> None:
    assert render_docx({"title": "Only title"})[:2] == b"PK"
    assert render_pptx({"slides": []})[:2] == b"PK"


def test_parse_pptx_block_then_render_attaches_file() -> None:
    text = 'A deck:\n```pptx\n{"title": "T", "slides": [{"title": "S", "bullets": ["a"]}]}\n```'
    intro, artifacts = parse_artifacts(text)
    assert intro == "A deck:"
    assert artifacts[0]["kind"] == "pptx"
    assert artifacts[0]["spec"]["title"] == "T"

    _render_file_artifacts(artifacts, "Presentation")
    a = artifacts[0]
    assert a["file_base64"]
    assert a["filename"].endswith(".pptx")
    assert a["mime"].endswith("presentationml.presentation")
    assert a["spec"] is None  # spec cleared once rendered


def test_parse_docx_block_renders() -> None:
    text = '```docx\n{"title": "Doc", "sections": [{"heading": "H", "paragraphs": ["p"]}]}\n```'
    _, artifacts = parse_artifacts(text)
    _render_file_artifacts(artifacts, "Report")
    assert artifacts[0]["kind"] == "docx"
    assert artifacts[0]["filename"].endswith(".docx")
    assert artifacts[0]["file_base64"]
