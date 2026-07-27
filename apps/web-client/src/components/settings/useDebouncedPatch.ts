import { useCallback, useEffect, useRef } from "react";
import type { SettingsValues } from "../../lib/api";

/**
 * Coalesce rapid preference edits into one PATCH.
 *
 * A range input fires onChange on every step of a drag; patching directly meant
 * one HTTP request and one JSON file write per 0.1 of temperature. Controls hold
 * their own local value for responsiveness and call this to persist.
 *
 * `patch` and `delayMs` are read through refs, so `push` and `flush` are stable
 * for the lifetime of the hook. That matters: an unstable `patch` (an inline
 * arrow from the caller, which is the normal case) previously invalidated
 * `flush` on every render, and the unmount effect keyed on it then fired as a
 * *render* cleanup — flushing immediately and defeating the debounce entirely.
 *
 * Contract on teardown: pending changes are flushed when this hook's owner
 * unmounts. That is *not* the same as "flushed when the dialog is dismissed" —
 * a panel that stays mounted and merely receives `open={false}` never unmounts.
 * Callers that can be hidden without unmounting must call the returned `flush`
 * themselves on close.
 */
export function useDebouncedPatch(
  patch: (changes: SettingsValues) => void,
  delayMs = 300,
): { push: (changes: SettingsValues) => void; flush: () => void } {
  const pending = useRef<SettingsValues>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const patchRef = useRef(patch);
  const delayRef = useRef(delayMs);

  useEffect(() => {
    patchRef.current = patch;
    delayRef.current = delayMs;
  });

  const flush = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    if (Object.keys(pending.current).length === 0) return;
    const changes = pending.current;
    pending.current = {};
    patchRef.current(changes);
  }, []);

  const push = useCallback(
    (changes: SettingsValues) => {
      // Merge by key: different keys within one window coalesce into a single
      // PATCH, the same key last-wins.
      pending.current = { ...pending.current, ...changes };
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(flush, delayRef.current);
    },
    [flush],
  );

  // `flush` is stable, so this cleanup runs on unmount only — never between
  // renders.
  useEffect(() => () => flush(), [flush]);

  return { push, flush };
}
