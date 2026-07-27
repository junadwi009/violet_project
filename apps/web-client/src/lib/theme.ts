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

function prefersDark(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
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

export function appearanceFromSettings(values: SettingsValues): Appearance {
  return {
    theme: (values.theme as ThemeChoice) ?? DEFAULT_APPEARANCE.theme,
    density: (values.ui_density as DensityChoice) ?? DEFAULT_APPEARANCE.density,
    fontScale: Number(values.font_scale ?? DEFAULT_APPEARANCE.fontScale),
    accent: (values.accent as AccentChoice) ?? DEFAULT_APPEARANCE.accent,
  };
}

export function readCachedAppearance(): Appearance {
  try {
    const raw = window.localStorage.getItem(CACHE_KEY);
    if (!raw) return DEFAULT_APPEARANCE;
    return { ...DEFAULT_APPEARANCE, ...(JSON.parse(raw) as Partial<Appearance>) };
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
