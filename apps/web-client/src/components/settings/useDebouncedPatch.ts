import { useCallback, useEffect, useRef } from "react";
import type { SettingsValues } from "../../lib/api";

/**
 * Coalesce rapid preference edits into one PATCH.
 *
 * A range input fires onChange on every step of a drag; patching directly meant
 * one HTTP request and one JSON file write per 0.1 of temperature. Controls hold
 * their own local value for responsiveness and call this to persist.
 */
export function useDebouncedPatch(
  patch: (changes: SettingsValues) => void,
  delayMs = 300,
): { push: (changes: SettingsValues) => void; flush: () => void } {
  const pending = useRef<SettingsValues>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    if (Object.keys(pending.current).length === 0) return;
    const changes = pending.current;
    pending.current = {};
    patch(changes);
  }, [patch]);

  const push = useCallback(
    (changes: SettingsValues) => {
      pending.current = { ...pending.current, ...changes };
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(flush, delayMs);
    },
    [delayMs, flush],
  );

  // Flush on unmount so a value typed and immediately dismissed is not lost.
  useEffect(() => flush, [flush]);

  return { push, flush };
}
