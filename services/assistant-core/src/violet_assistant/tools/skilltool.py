"""Skill governance CLI.

    python -m violet_assistant.tools.skilltool check <path/to/SKILL.md> [--judge]
    python -m violet_assistant.tools.skilltool merge <id|path> <id|path> ... --name NAME [--out FILE]

`check` vets a candidate skill against the installed library (rule-based always; add --judge for an
LLM quality/novelty verdict). `merge` combines skills into one improved SKILL.md.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from violet_assistant.agents.registry import AgentRegistry
from violet_assistant.agents.schema import Agent
from violet_assistant.agents.vetting import (
    batch_report,
    build_library,
    judge_candidate,
    load_candidate,
    merge_skills,
    nearest_matches,
    rule_verdict,
)
from violet_assistant.config import load_settings
from violet_assistant.llm.openai_compatible_provider import OpenAICompatibleProvider
from violet_assistant.skills.registry import SkillRegistry


def _registries(settings):
    skills = SkillRegistry(settings.skills_config_dir or (settings.repo_root / "configs" / "skills"))
    agents = AgentRegistry(
        settings.agents_config_dir or (settings.repo_root / "configs" / "agents"),
        default_model=settings.agent_default_model,
    )
    return skills, agents


def _provider(settings):
    if not settings.agent_api_key:
        return None
    return OpenAICompatibleProvider(
        base_url=settings.agent_base_url,
        api_key=settings.agent_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        default_headers={"HTTP-Referer": "https://localhost/violet", "X-Title": "Violet"},
    )


def _resolve_skill(ref: str, agents: AgentRegistry, default_model: str) -> Agent:
    got = agents.get(ref)
    if got is not None:
        return got
    return load_candidate(ref, default_model)


def cmd_check(args, settings) -> int:
    skills, agents = _registries(settings)
    candidate = load_candidate(args.path, settings.agent_default_model)
    library = build_library(skills, agents)
    matches = nearest_matches(candidate, library)
    verdict = rule_verdict(candidate, matches)

    print(f"Candidate: {candidate.name}  ({len(candidate.system_prompt)} chars, "
          f"{len(candidate.triggers)} triggers)")
    print(f"Rule verdict: {verdict['verdict'].upper()} - {verdict['reason']}")
    print("Nearest in library:")
    for m in matches:
        print(f"  {m.similarity:>5}  {m.entry.kind}:{m.entry.id}"
              + (f"  (shared triggers: {m.shared_triggers})" if m.shared_triggers else ""))

    if args.judge:
        provider = _provider(settings)
        if provider is None:
            print("\n[--judge skipped: no agent/OpenRouter key configured]")
        else:
            result = asyncio.run(
                judge_candidate(candidate, library, provider, settings.agent_default_model)
            )
            print(f"\nLLM verdict: {str(result.get('verdict','?')).upper()} "
                  f"(closest: {result.get('closest','none')})\n  {result.get('reason','')}")
    return 0


def cmd_batch(args, settings) -> int:
    skills, agents = _registries(settings)
    library = build_library(skills, agents)
    installed_ids = {e.id for e in library if e.kind == "agent"}
    provider = _provider(settings) if args.judge else None

    paths = sorted(Path(args.dir).rglob("SKILL.md"))
    candidates: list[Agent] = []
    invalid: list[tuple[str, str]] = []
    for p in paths:
        try:
            candidates.append(load_candidate(p, settings.agent_default_model))
        except (ValueError, OSError) as exc:
            invalid.append((p.parent.name, str(exc)[:50]))

    rows = batch_report(candidates, library, installed_ids)
    by_id = {c.id: c for c in candidates}

    print(f"Checked {len(paths)} skill(s) in {args.dir} against {len(library)} installed.\n")
    header = f"{'skill':28} {'status':11} {'nearest':22} {'llm':11}"
    print(header)
    print("-" * len(header))
    recommend, skip = [], []
    for row in rows:
        llm = ""
        if provider is not None and not row["installed"]:
            result = asyncio.run(
                judge_candidate(by_id[row["id"]], library, provider, settings.agent_default_model)
            )
            llm = str(result.get("verdict", "?"))
        status = "installed" if row["installed"] else row["rule"]
        nearest = f"{row['nearest']} ({row['similarity']})" if row["nearest"] else "-"
        print(f"{row['id'][:28]:28} {status:11} {nearest[:22]:22} {llm:11}")
        if not row["installed"]:
            decision = llm or row["rule"]
            if decision in ("redundant", "low_quality"):
                skip.append(row["id"])
            elif decision in ("keep", "novel", "overlaps"):
                recommend.append(row["id"])
    for name, reason in invalid:
        print(f"{name[:28]:28} {'invalid':11} {reason[:22]:22}")

    print("\nRecommendation:")
    print(f"  import  : {', '.join(recommend) or '(none new)'}")
    print(f"  skip    : {', '.join(skip) or '(none)'}")
    if invalid:
        print(f"  invalid : {', '.join(n for n, _ in invalid)}")
    return 0


def cmd_merge(args, settings) -> int:
    _, agents = _registries(settings)
    provider = _provider(settings)
    if provider is None:
        print("merge needs an OpenRouter/agent key (set OPENROUTER_API_KEY).")
        return 2
    to_merge = [_resolve_skill(ref, agents, settings.agent_default_model) for ref in args.refs]
    merged = asyncio.run(
        merge_skills(to_merge, args.name, provider, settings.agent_default_model)
    )
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(merged, encoding="utf-8")
        print(f"Merged {len(to_merge)} skills -> {args.out}")
    else:
        print(merged)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skilltool")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Vet a candidate skill against the installed library.")
    check.add_argument("path", help="Path to a candidate SKILL.md")
    check.add_argument("--judge", action="store_true", help="Also run an LLM quality/novelty verdict")

    batch = sub.add_parser("batch", help="Vet every SKILL.md under a directory.")
    batch.add_argument("dir", help="Directory to scan for SKILL.md files (recursive)")
    batch.add_argument("--judge", action="store_true", help="Add an LLM verdict per candidate")

    merge = sub.add_parser("merge", help="Combine skills into one improved SKILL.md.")
    merge.add_argument("refs", nargs="+", help="Skill/agent ids or SKILL.md paths to combine")
    merge.add_argument("--name", required=True, help="Name for the merged skill")
    merge.add_argument("--out", help="Write the merged SKILL.md here (else print)")

    args = parser.parse_args(argv)
    settings = load_settings()
    if args.command == "check":
        return cmd_check(args, settings)
    if args.command == "batch":
        return cmd_batch(args, settings)
    return cmd_merge(args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
