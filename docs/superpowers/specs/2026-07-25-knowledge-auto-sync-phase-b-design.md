# Design — Knowledge Auto-Sync (Phase B)

Date: 2026-07-25
Status: Approved (brainstorming → spec/plan)
Scope: `project_violet` (assistant-core backend + web-client frontend)
Depends on: Phase A (indexer/store/retriever) + Phase C (source abstraction,
`reindex(only=...)`, per-source status).

## Summary

Background auto-sync so the user never has to click Reindex/Sync. A single
async polling loop re-runs the **incremental** reindex on a cadence: the local
folder on a fast interval, Google Drive on a slower one (to respect Drive API
quota). Controlled by a **runtime preference** (`knowledge_auto_sync`, default
off) read live each tick, plus a last-sync status surfaced in the UI. No new
dependencies — stdlib `asyncio`/`time` over the existing async indexer.

## Components

### `knowledge/auto_sync.py` — `AutoSyncScheduler`
```python
class AutoSyncScheduler:
    def __init__(self, indexer, preferences, settings): ...
    def enabled(self) -> bool                     # reads the knowledge_auto_sync pref live
    async def run_due(self, now: float) -> dict    # runs local each call; gdrive when its interval elapsed
    def status(self) -> dict                       # {enabled, interval, gdrive_interval, last_sync:{local, gdrive}}
    async def start(self) -> None                  # launches the loop task
    async def stop(self) -> None                   # cancels the loop task
```
- **Cadence:** the loop ticks every `knowledge_sync_interval_seconds` (default 30).
  On each tick, if `enabled()`:
  - always run `indexer.reindex(only="local")` (incremental — cheap when nothing
    changed);
  - run `indexer.reindex(only="gdrive")` only when
    `now - last_gdrive >= gdrive_sync_interval_seconds` (default 300) **and** a
    gdrive source exists.
- **Overlap guard:** an `asyncio.Lock`; if a run is still in progress when the
  next tick fires, that tick is skipped (`{"skipped": "in_progress"}`).
- **Resilience:** each run wrapped in try/except; a failure is recorded in
  `last_sync[...].error` and the loop continues. Never crashes.
- **State:** `last_sync[source] = {at: ISO8601, indexed, skipped, removed,
  chunks, error?}` (monotonic timestamps drive the cadence; wall-clock ISO is for
  display). `now` is injected into `run_due` so it is unit-testable without real
  time.

### Preference + config
- New editable preference `knowledge_auto_sync` (bool), default =
  `settings.knowledge_auto_sync`. Toggled from the UI, read live by the loop.
- New `Settings` fields (env):
  | Env | Default | Meaning |
  |---|---|---|
  | `KNOWLEDGE_AUTO_SYNC` | `false` | seeds the preference default |
  | `KNOWLEDGE_SYNC_INTERVAL_SECONDS` | `30` | loop tick / local cadence |
  | `GDRIVE_SYNC_INTERVAL_SECONDS` | `300` | Drive cadence |

### App wiring
- Build the scheduler in `create_app` when RAG is active; start it on the
  FastAPI **startup** event and stop it on **shutdown** (runs inside uvicorn's
  loop). Guarded so a missing scheduler is a no-op.
- The existing synchronous startup scan is unchanged; the scheduler handles
  ongoing syncs.

### Routes
- `GET /api/knowledge` gains an `auto_sync` block from `scheduler.status()`
  (enabled, intervals, per-source last-sync). No new endpoints — the toggle uses
  the existing `PATCH /api/settings` (`knowledge_auto_sync`).

### Frontend
- Knowledge section: an **Auto-sync** toggle (bound to the `knowledge_auto_sync`
  preference via `onPatchSettings`), always visible (simple behavior toggle).
- Show each source's **last synced** time (from `auto_sync.last_sync`) next to
  its status row. A subtle "auto" badge when enabled.

## Error handling
- Reindex failure in a tick → recorded in `last_sync[...].error`, loop continues.
- Auto-sync toggled off → loop keeps ticking but does nothing (cheap); no restart
  needed.
- Scheduler absent (RAG off) → `auto_sync` block reports `{enabled: false}`.

## Testing
- `AutoSyncScheduler.run_due` with a **fake indexer** + injected `now`:
  - disabled pref → no reindex calls;
  - enabled → local runs every call;
  - gdrive runs only after `gdrive_sync_interval_seconds` elapses (advance `now`);
  - overlap: a second `run_due` while the lock is held returns `in_progress`;
  - a raising indexer records an error and doesn't propagate.
- `status()` shape; preference default seeds from settings.
- Routes: `GET /api/knowledge` includes `auto_sync` (direct endpoint call).
- Frontend: `npm run build`.

The loop task itself (`start`/`stop`/sleep) is thin and not unit-tested; the
tested `run_due` carries the logic.

## Build order
1. Preference `knowledge_auto_sync` + `Settings` fields.
2. `AutoSyncScheduler` (`enabled`, `run_due`, `status`, overlap lock) + tests.
3. App wiring (startup/shutdown) + `auto_sync` in `GET /api/knowledge`.
4. Frontend: Auto-sync toggle + last-sync display.

Each unit: tests + a `logs/{update}_{date}_log.md` entry before commit.

## Out of scope
Real-time filesystem events (watchdog), Drive push webhooks, per-file change
cursors (Drive changes API), backoff/jitter tuning, multi-folder scheduling.
