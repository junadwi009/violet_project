from __future__ import annotations

import pytest

from violet_assistant.agents.schema import Agent
from violet_assistant.agents.vetting import (
    LibraryEntry,
    _terms,
    batch_report,
    load_candidate,
    nearest_matches,
    rule_verdict,
)


def _entry(id, name, desc, triggers):
    return LibraryEntry(id, "skill", name, desc, triggers, _terms(name, desc, triggers))


LIBRARY = [
    _entry("dashboard", "Interactive Dashboard", "Build an interactive HTML report dashboard.", ["dashboard", "report"]),
    _entry("chart", "Chart", "Turn data into a chart (bar line pie).", ["chart", "graph"]),
    _entry("researcher", "Researcher", "Deep research and reasoning.", ["research", "deep dive"]),
]


def test_duplicate_is_flagged_redundant() -> None:
    candidate = Agent(
        id="web-dashboards",
        name="Dashboard Builder",
        model="m",
        system_prompt="You build interactive HTML report dashboards from data. " * 5,
        description="Create an interactive HTML report dashboard from data.",
        triggers=["dashboard", "report"],
    )
    matches = nearest_matches(candidate, LIBRARY)
    verdict = rule_verdict(candidate, matches)
    assert matches[0].entry.id == "dashboard"
    assert verdict["verdict"] == "redundant"
    assert "dashboard" in matches[0].shared_triggers


def test_novel_skill_is_flagged_novel() -> None:
    candidate = Agent(
        id="translator",
        name="Translator",
        model="m",
        system_prompt="You translate text between languages faithfully and idiomatically. " * 4,
        description="Translate text between languages.",
        triggers=["translate", "translation"],
    )
    verdict = rule_verdict(candidate, nearest_matches(candidate, LIBRARY))
    assert verdict["verdict"] == "novel"


def test_batch_report_flags_installed_and_duplicates() -> None:
    dup = Agent(
        id="charts", name="Chart Maker", model="m",
        system_prompt="Turn data into a chart, bar line pie graph. " * 4,
        description="Turn data into a chart (bar line pie graph).",
        triggers=["chart", "graph"],
    )
    novel = Agent(
        id="translator", name="Translator", model="m",
        system_prompt="Translate text between languages faithfully. " * 4,
        description="Translate text between languages.", triggers=["translate"],
    )
    rows = batch_report([dup, novel], LIBRARY, installed_ids={"researcher"})
    by_id = {r["id"]: r for r in rows}
    assert by_id["charts"]["rule"] == "redundant"
    assert by_id["charts"]["nearest"] == "chart"
    assert by_id["translator"]["rule"] == "novel"
    assert by_id["charts"]["installed"] is False


def test_install_skill_writes_and_is_loadable(tmp_path) -> None:
    from violet_assistant.agents.registry import AgentRegistry
    from violet_assistant.agents.vetting import install_skill

    imported = tmp_path / "agents" / "imported"
    md = (
        "---\nname: Summarizer\ndescription: Summarize text.\ntriggers: summarize\n---\n"
        "You produce faithful, concise summaries of the input text."
    )
    result = install_skill(md, imported, default_model="hermes")
    assert result["id"] == "summarizer"
    assert result["updated"] is False
    assert (imported / "summarizer" / "SKILL.md").exists()

    # the agents dir now contains it -> registry loads it (live)
    reg = AgentRegistry(tmp_path / "agents", default_model="hermes")
    assert reg.get("summarizer") is not None
    assert reg.detect("please summarize this").id == "summarizer"

    # re-install marks updated
    assert install_skill(md, imported, "hermes")["updated"] is True


def test_install_skill_rejects_invalid(tmp_path) -> None:
    from violet_assistant.agents.vetting import install_skill

    with pytest.raises(ValueError):
        install_skill("---\nname: X\ndescription: y\n---\n", tmp_path, "m")


def test_load_candidate_rejects_empty(tmp_path) -> None:
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: Empty\ndescription: nothing\n---\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_candidate(p, default_model="m")


def test_candidate_from_text_valid_and_invalid() -> None:
    from violet_assistant.agents.vetting import candidate_from_text

    good = candidate_from_text(
        "---\nname: Foo\ndescription: d\n---\n" + "You do a specific useful thing well. " * 4,
        "fb", "m",
    )
    assert good.name == "Foo"
    with pytest.raises(ValueError):
        candidate_from_text("---\nname: Bar\ndescription: d\n---\n", "fb", "m")


def test_resolve_ref_from_both_registries() -> None:
    from pathlib import Path

    from violet_assistant.agents.registry import AgentRegistry
    from violet_assistant.agents.vetting import resolve_ref
    from violet_assistant.skills.registry import SkillRegistry

    root = Path(__file__).resolve().parents[3]
    skills = SkillRegistry(root / "configs" / "skills")
    agents = AgentRegistry(root / "configs" / "agents", default_model="m")

    assert resolve_ref("writer", skills, agents, "m").id == "writer"  # native agent
    chart = resolve_ref("chart", skills, agents, "m")  # skill wrapped as agent
    assert chart is not None and chart.id == "chart" and chart.system_prompt
    assert resolve_ref("does-not-exist", skills, agents, "m") is None


def test_load_candidate_parses_valid(tmp_path) -> None:
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: Summarizer\ndescription: Summarize long text.\n---\n"
        "You produce faithful, concise summaries of long input text, preserving key facts.",
        encoding="utf-8",
    )
    candidate = load_candidate(p, default_model="hermes")
    assert candidate.name == "Summarizer"
    assert candidate.model == "hermes"
