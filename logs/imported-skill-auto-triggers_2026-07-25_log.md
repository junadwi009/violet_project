# Phase 3h — Auto-triggers for imported skills

- **Date:** 2026-07-25
- **Track:** skills routing
- **Branch:** main
- **Author:** Claude Code

## What
Made imported SKILL.md skills auto-detect (not only explicit-select) by deriving triggers from the
skill's name + description, and by adding hand-authored natural triggers to the 6 imported skills.

## Changes
- `agents/skillmd.py` — `_derive_triggers(description)`: emits specific multi-word (bigram) triggers
  from the description (skips stopwords + short words) so future imports get some auto-detection.
  `parse_skill_md` now combines explicit `triggers:`/`keywords:` frontmatter + the name + derived
  bigrams (capped at 10).
- Added natural `triggers:` frontmatter to the 6 imported skills (internal-comms, doc-coauthoring,
  frontend-design, mcp-builder, skill-creator, canvas-design) — deterministic, no per-request cost.

## Why
Description-prose bigrams alone don't match how users phrase requests (e.g. "internal communications"
won't match "internal communication"). Hand-authored triggers on the batch give reliable routing;
the derived bigrams remain a fallback for future imports.

## Status
done — tests green, routing verified.

## Verification
- `python -m pytest` → **64 passed**.
- Auto-detection (registry): "write an internal announcement for the team" → internal-comms;
  "help me co-author a document" → doc-coauthoring; "design a landing page" → frontend-design;
  "build an mcp server" → mcp-builder; "create a new skill" → skill-creator; "design a poster …" →
  canvas-design.
- No false positives: "what is the weather today" / "summarize this article" / "hello violet" → None
  (fall through to the cascade).

## Next
Optional: an LLM-assisted trigger generator (`gen-triggers` CLI) to auto-write high-quality triggers
for any bulk-imported skill; relax matching (stemming) for multi-word triggers.
