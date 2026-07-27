# ModelResolver — review fixes (wiring regression tests + key guard)

- **Date:** 2026-07-27
- **Track:** cross-cutting (settings / model resolution)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What
Fix pass on Task 3 review findings. Added five tests that pin the `ModelResolver` wiring
(`CascadeResponder`, `SkillEngine`, `VisionOCR`, and all four `create_app()` construction
sites), made the `AgentRegistry` test's first assertion non-tautological by constructing with
a sentinel `default_model`, and gave `ModelResolver.resolve()` an explicit key guard.

## Why
A reviewer proved by mutation that reverting `CascadeResponder`, `SkillEngine`, and `VisionOCR`
to ignore the resolver, or stripping all four `resolver=model_resolver,` arguments from
`main.py`, still passed all 207 tests. The threading that makes a model-id edit take effect
without a restart had no regression protection at all. Separately, `resolve()` leaked a bare
`AttributeError` from `getattr(settings, key)` on a mistyped key, and the registry test's first
assertion compared two values that happen to be equal by default.

## Files touched
- `services/assistant-core/src/violet_assistant/preferences/resolver.py` — `hasattr` guard in
  `resolve()` raising a named `KeyError`.
- `services/assistant-core/tests/test_model_resolver.py` — sentinel in the registry test; five
  new tests; shared `_RecordingProvider` helper.

No shared-seam production file changed; the only production edit is a guard clause that raises
where the previous code already raised.

## Interfaces / contracts changed
`ModelResolver.resolve()` now raises `KeyError` (was: `AttributeError`) for a key that is not a
`Settings` attribute. All five call sites use valid keys, so no behavior change in practice.
No new preference keys. No component's `resolver=None` behavior changed.

## Status
done

## Verification
- `python -m pytest` → **212 passed, 8 warnings in 9.93s** (207 pre-existing + 5 new).
- Mutation checks — each new test was proved to discriminate by breaking the corresponding
  wiring, confirming failure, restoring, and confirming pass. See
  `.superpowers/sdd/task-3-report.md` § Fix pass for the full matrix.

## Next
- The five model-id fields still have no UI (later task in the settings overhaul).
- Consider a `typing.Protocol` for the untyped `resolver=None` parameters.
