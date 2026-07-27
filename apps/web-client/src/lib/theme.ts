import type { SettingsValues } from "./api";

export type ThemeChoice = "light" | "dark" | "system";
export type DensityChoice = "cozy" | "compact";
export type AccentChoice = "violet" | "indigo" | "teal" | "amber" | "rose";

export type Appearance = {
  theme: ThemeChoice;
  density: DensityChoice;
  fontScale: number;
  accent: AccentChoice;
};

export const DEFAULT_APPEARANCE: Appearance = {
  theme: "system",
  density: "cozy",
  fontScale: 1,
  accent: "violet",
};

const CACHE_KEY = "violet.appearance";

export const MIN_FONT_SCALE = 0.875;
export const MAX_FONT_SCALE = 1.25;

/**
 * Coerce anything into a usable font scale.
 *
 * This is a safety clamp, not a convenience. `html { font-size: calc(1rem *
 * var(--font-scale)) }` renders at **0px** for `NaN`, `0` or a negative value —
 * `NaN` is a *valid* calc token that clamps to zero for a non-negative length,
 * so there is no "invalid declaration" fallback to save us. At 0px every rem
 * utility collapses, including the Appearance panel the user would need to
 * undo it. `1e400` is the mirror image: Infinity, an 8000px root.
 *
 * Neither input is trustworthy. The server validates on write but
 * `PreferencesStore.effective()` re-reads preferences.json and filters by key
 * name only, so a hand-edited or stale file flows straight through; and
 * localStorage sits outside server validation entirely.
 */
export function clampFontScale(value: unknown): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return DEFAULT_APPEARANCE.fontScale;
  return Math.min(MAX_FONT_SCALE, Math.max(MIN_FONT_SCALE, n));
}

function prefersDark(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

const THEME_VALUES: readonly ThemeChoice[] = ["light", "dark", "system"];
const DENSITY_VALUES: readonly DensityChoice[] = ["cozy", "compact"];
const ACCENT_VALUES: readonly AccentChoice[] = ["violet", "indigo", "teal", "amber", "rose"];

/**
 * Coerce anything into a known theme. Same rationale as `clampFontScale`:
 * the server validates on write but `PreferencesStore.effective()` re-reads
 * preferences.json and filters by key name only, so a bad value (hand-edited
 * file, stale cache) reaches the client verbatim. Unlike `??`, this also
 * catches a *present* bad value, not just `null`/`undefined` — `"purple"`
 * must not be handed to `applyAppearance`, which stamps it onto `<html>`
 * with no matching CSS rule, or to the `theme !== "system"` check that
 * decides whether to subscribe to OS theme changes.
 */
function coerceTheme(value: unknown): ThemeChoice {
  return (THEME_VALUES as readonly unknown[]).includes(value)
    ? (value as ThemeChoice)
    : DEFAULT_APPEARANCE.theme;
}

function coerceDensity(value: unknown): DensityChoice {
  return (DENSITY_VALUES as readonly unknown[]).includes(value)
    ? (value as DensityChoice)
    : DEFAULT_APPEARANCE.density;
}

function coerceAccent(value: unknown): AccentChoice {
  return (ACCENT_VALUES as readonly unknown[]).includes(value)
    ? (value as AccentChoice)
    : DEFAULT_APPEARANCE.accent;
}

/** Stamp the appearance onto <html>. Everything else is CSS. */
export function applyAppearance(appearance: Appearance): void {
  const root = document.documentElement;
  const resolved =
    appearance.theme === "system"
      ? prefersDark()
        ? "dark"
        : "light"
      : appearance.theme;
  root.dataset.theme = resolved;
  root.dataset.density = appearance.density;
  root.dataset.accent = appearance.accent;
  root.style.setProperty("--font-scale", String(appearance.fontScale));
}

/**
 * The single source of truth for turning raw server settings into a
 * validated `Appearance`. Both the painted page (`App.tsx`) and the
 * Appearance panel derive from this function, so they can never disagree
 * about what a bad value should display as.
 */
export function appearanceFromSettings(values: SettingsValues): Appearance {
  return {
    theme: coerceTheme(values.theme),
    density: coerceDensity(values.ui_density),
    fontScale: clampFontScale(values.font_scale ?? DEFAULT_APPEARANCE.fontScale),
    accent: coerceAccent(values.accent),
  };
}

export function readCachedAppearance(): Appearance {
  try {
    const raw = window.localStorage.getItem(CACHE_KEY);
    if (!raw) return DEFAULT_APPEARANCE;
    const cached = JSON.parse(raw) as Partial<Appearance>;
    // The DEFAULT_APPEARANCE spread only fills in *absent* keys — it cannot
    // protect against a key that is present and bad, and localStorage never
    // passed through server validation. Clamp explicitly.
    return {
      ...DEFAULT_APPEARANCE,
      ...cached,
      fontScale: clampFontScale(cached.fontScale ?? DEFAULT_APPEARANCE.fontScale),
    };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

/** The cache is a paint hint only — the server value always overwrites it. */
export function writeCachedAppearance(appearance: Appearance): void {
  try {
    window.localStorage.setItem(CACHE_KEY, JSON.stringify(appearance));
  } catch {
    /* private browsing or a full quota — the server value still applies */
  }
}

/** Track OS theme changes while theme === "system". Returns an unsubscribe. */
export function watchSystemTheme(onChange: () => void): () => void {
  const query = window.matchMedia?.("(prefers-color-scheme: dark)");
  if (!query) return () => {};
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
