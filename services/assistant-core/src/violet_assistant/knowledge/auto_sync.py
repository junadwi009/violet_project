from __future__ import annotations

import asyncio
import datetime


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class AutoSyncScheduler:
    """Background loop that re-runs the incremental reindex on a cadence.

    Local runs every tick; Google Drive on a slower interval. Enabled/disabled
    live via the ``knowledge_auto_sync`` preference. Cadence logic lives in
    ``run_due(now)`` (injected time) so it is unit-testable without sleeping.
    """

    def __init__(self, indexer, preferences, settings) -> None:
        self.indexer = indexer
        self.preferences = preferences
        self.settings = settings
        self.interval = settings.knowledge_sync_interval_seconds
        self.gdrive_interval = settings.gdrive_sync_interval_seconds
        self._lock = asyncio.Lock()
        self._last_gdrive: float | None = None
        self._last_result: dict = {"local": None, "gdrive": None}
        self._task: asyncio.Task | None = None
        self._stopped = False

    def enabled(self) -> bool:
        if self.preferences is None:
            return bool(self.settings.knowledge_auto_sync)
        return bool(
            self.preferences.effective(self.settings).get("knowledge_auto_sync", False)
        )

    def _has_gdrive(self) -> bool:
        return any(getattr(s, "name", "") == "gdrive" for s in self.indexer.sources)

    async def _sync(self, origin: str) -> None:
        try:
            report = await self.indexer.reindex(only=origin)
            per = report.get("sources", {}).get(origin, report)
            self._last_result[origin] = {
                "at": _now_iso(),
                "indexed": per.get("indexed", 0),
                "skipped": per.get("skipped", 0),
                "removed": per.get("removed", 0),
                "chunks": per.get("chunks", 0),
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 — one bad sync must not kill the loop
            self._last_result[origin] = {"at": _now_iso(), "error": str(exc)}

    async def run_due(self, now: float) -> dict:
        if not self.enabled():
            return {"ran": []}
        if self._lock.locked():
            return {"skipped": "in_progress"}
        ran: list[str] = []
        async with self._lock:
            await self._sync("local")
            ran.append("local")
            if self._has_gdrive() and (
                self._last_gdrive is None
                or now - self._last_gdrive >= self.gdrive_interval
            ):
                await self._sync("gdrive")
                self._last_gdrive = now
                ran.append("gdrive")
        return {"ran": ran}

    def status(self) -> dict:
        return {
            "enabled": self.enabled(),
            "interval": self.interval,
            "gdrive_interval": self.gdrive_interval,
            "last_sync": dict(self._last_result),
        }

    async def _loop(self) -> None:
        import time

        while not self._stopped:
            await asyncio.sleep(self.interval)
            try:
                await self.run_due(time.monotonic())
            except Exception:  # noqa: BLE001 — the loop must never die
                pass

    async def start(self) -> None:
        if self._task is None:
            self._stopped = False
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
