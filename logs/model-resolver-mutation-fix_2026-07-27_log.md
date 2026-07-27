# Model resolver cascade delegation test coverage

- **Date:** 2026-07-27
- **Track:** cross-cutting (settings overhaul / test safety net)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What
Widened `test_model_resolver.py`'s `_RecordingProvider` to accept a queue of replies
(one per call), and added `test_cascade_uses_resolver_for_technical_model_when_delegated`
which drives `CascadeResponder.respond()` through the delegated path (first persona
reply starts with `DELEGATE:`, second is the composed reply). Also hardened
`test_create_app_wires_the_resolver`'s migration copy loop with an explicit
`assert source.exists()` instead of silently skipping a renamed migration file.

## Why
`test_cascade_uses_resolver_for_persona_model` only ever hit the non-delegated
early-return branch of `CascadeResponder.respond()`, so 3 of 5 model-substitution
sites (`_technical_model()`, the composed persona call, and the delegated
`models_used` list) had zero regression protection — three mutations there survived
the full suite undetected. `technical_model` is one of the five preference keys this
work exists to deliver.

## Files touched
- `services/assistant-core/tests/test_model_resolver.py`

## Interfaces / contracts changed
None — test-only change. `cascade.py` and `resolver.py` were not modified.

## Status
done

## Verification
- `python -m pytest` → 213 passed (212 baseline + 1 new test), all green.
- Mutation testing (each applied to `cascade.py`, confirmed failing test, then reverted):
  1. `_technical_model()` reverted to ignore the resolver (`return self.technical.model`
     unconditionally) → `test_cascade_uses_resolver_for_technical_model_when_delegated`
     FAILED. Reverted → suite green again.
  2. Composed persona call's `LLMOptions(model=persona_model, ...)` reverted to
     `LLMOptions(model=self.persona.model, ...)` → same test FAILED. Reverted → green.
  3. Delegated `models_used=[persona_model, technical_model, persona_model]` reverted to
     `models_used=[self.persona.model, self.technical.model, self.persona.model]` →
     same test FAILED. Reverted → green.
- `git diff --stat` on `cascade.py` confirmed clean (no residual mutation) before
  committing.

## Next
None — safety net for `technical_model` and the delegated composition path is now in
place alongside the other four resolver wiring tests.
