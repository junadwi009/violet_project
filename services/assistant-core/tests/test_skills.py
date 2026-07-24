from __future__ import annotations

import json
from pathlib import Path

from violet_assistant.skills.generator import parse_artifacts
from violet_assistant.skills.registry import SkillRegistry
from violet_assistant.skills.schema import Skill


def _write_skill(tmp_path: Path, skill: dict) -> Path:
    d = tmp_path / "skills"
    d.mkdir(exist_ok=True)
    (d / f"{skill['id']}.json").write_text(json.dumps(skill), encoding="utf-8")
    return d


def test_registry_detects_by_trigger(tmp_path) -> None:
    d = _write_skill(
        tmp_path,
        {"id": "chart", "name": "Chart", "kind": "chartjs", "triggers": ["chart", "graph"], "prompt": "p"},
    )
    registry = SkillRegistry(d)
    assert registry.detect("make me a bar chart of sales").id == "chart"
    assert registry.detect("just chatting about the weather") is None


def test_skill_matches_case_insensitive() -> None:
    skill = Skill(id="dashboard", name="Dashboard", kind="html", triggers=["dashboard"], prompt="p")
    assert skill.matches("Build a DASHBOARD please")
    assert not skill.matches("hello there")


def test_parse_chartjs_artifact() -> None:
    text = (
        "Here's your chart.\n"
        '```chartjs\n{"type": "bar", "data": {"labels": ["A"], "datasets": [{"data": [1]}]}}\n```'
    )
    intro, artifacts = parse_artifacts(text)
    assert intro == "Here's your chart."
    assert len(artifacts) == 1
    assert artifacts[0]["kind"] == "chartjs"
    assert artifacts[0]["spec"]["type"] == "bar"
    assert artifacts[0]["html"] is None


def test_parse_html_artifact() -> None:
    text = "A dashboard:\n```html\n<div id=\"app\">hi</div><script>1+1</script>\n```"
    intro, artifacts = parse_artifacts(text)
    assert intro == "A dashboard:"
    assert artifacts[0]["kind"] == "html"
    assert "<div" in artifacts[0]["html"]
    assert artifacts[0]["spec"] is None


def test_parse_drops_invalid_chart_json() -> None:
    text = "oops\n```chartjs\n{not valid json,,,}\n```"
    intro, artifacts = parse_artifacts(text)
    assert artifacts == []
    assert intro == "oops"


def test_parse_plain_text_has_no_artifacts() -> None:
    intro, artifacts = parse_artifacts("just a normal answer")
    assert intro == "just a normal answer"
    assert artifacts == []
