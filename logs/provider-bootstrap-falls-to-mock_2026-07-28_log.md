# Provider bootstrap silently selected the offline mock provider

- **Date:** 2026-07-28
- **Track:** 1 Chat (web-client bootstrap)
- **Branch:** main (post-merge fix)
- **Author:** Claude

## What
Swapped two arguments at the provider bootstrap call to `resolveOffered` in
`apps/web-client/src/App.tsx`, so the server's active provider outranks the
hardcoded `useState("mock")` placeholder when the stored `default_provider`
names an id the registry does not offer.

## Why
Found by running the app rather than by testing it — the composer's engine chip
read **"Mock"** on a machine with a live OpenRouter key configured, and every
reply came back `"Violet mock response: … I am running in safe local mock mode,
so no external model or paid API was used."`

The chain:

1. `.env` sets `LLM_PROVIDER=ollama`, so `PreferencesStore._defaults()` seeds
   `default_provider` as `"ollama"`.
2. The provider registry exposes exactly two ids — `mock` and
   `openai_compatible` (labelled "Local / OpenAI-compatible"). **`ollama` is not
   among them**; it is an alias that only ever names the frozen `Settings`
   value.
3. `resolveOffered(desired, current, offered, fallback)` tries in order:
   `desired` → `current` → `fallback` → `offered[0]`.
4. At bootstrap `current` is still `useState("mock")`. So `desired` (`"ollama"`)
   misses, `current` (`"mock"`) **hits**, and the fallback — the server's own
   `providerResponse.active` (`"openai_compatible"`) — is never reached.
5. `ChatOrchestrator` short-circuits on `provider == "mock"` before the cascade
   branch, so the OpenRouter persona/technical layers were never called.

Net effect: an app configured with a paid API key ran entirely offline, and said
so only inside the reply text. The user hit this directly — two of their own
messages are in the database with mock responses.

`current` is a *placeholder* at bootstrap, not a choice, so preferring it over
the server's declared active provider was the wrong precedence. On the reset
path `current` **is** the user's real selection, so that call site is correct as
written and was left alone.

## Files touched
- `apps/web-client/src/App.tsx` — provider bootstrap call to `resolveOffered`;
  `providerResponse.active` and `current` swapped, with a comment recording the
  concrete `ollama`/`openai_compatible` mismatch that motivated it.

## Interfaces / contracts changed
None. `resolveOffered`'s signature and precedence rules are unchanged; only the
arguments passed at one call site moved.

## Status
done — fix verified at the selection layer; end-to-end chat left to the user
(see Verification).

## Verification
- Before: `GET /api/providers` → `active: openai_compatible`,
  `items: [mock, openai_compatible]`; `GET /api/settings` →
  `default_provider: "ollama"`; composer chip rendered **"Mock"**.
- After a reload on the running dev server, the chip renders **"Local"** — i.e.
  `openai_compatible`, the server's active provider — so the mock short-circuit
  no longer applies.
- `npm run build` PASS.
- **Not verified end to end.** Repeated attempts to send a message through the
  browser-automation pane failed to register (no `POST /api/chat` in the backend
  log, no console error), so a real OpenRouter round-trip was never observed by
  me. The user confirms the failing behaviour first-hand and is driving the
  confirmation of the fix.

## Next
Two follow-ups this exposed, neither fixed here:
- **`ollama` is not a real provider id.** `_defaults()` seeds `default_provider`
  from `settings.llm_provider`, which is a *configuration* value, while the
  registry publishes a different id space. Any `LLM_PROVIDER` value outside
  `{mock, openai_compatible}` produces an unresolvable `default_provider`. The
  seed should map through the registry, or the registry should expose the
  configured alias.
- **No test covers this.** The web client has no test runner, and the backend
  cannot see it — this is purely a client-side precedence bug. A test asserting
  "an unresolvable `default_provider` resolves to the server's active provider,
  never to `mock`" would need a frontend harness the project does not have.
