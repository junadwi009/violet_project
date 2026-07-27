/**
 * DOM ids shared between `SettingsNav` (which renders the `role="tab"` buttons)
 * and `SettingsShell` (which renders the `role="tabpanel"` region).
 *
 * The two halves live in different components but the ARIA tab pattern requires
 * them to point at each other (`aria-controls` / `aria-labelledby`), so the id
 * scheme has to be agreed on somewhere neither owns. `useId()` cannot do this
 * without threading a generated prefix through the caller, and the settings
 * dialog is a singleton, so a deterministic scheme is both sufficient and
 * easier to debug. If a second, simultaneously-mounted settings dialog ever
 * exists, this needs a prefix parameter.
 */
export function settingsTabDomId(tabId: string): string {
  return `settings-tab-${tabId}`;
}

export function settingsPanelDomId(tabId: string): string {
  return `settings-panel-${tabId}`;
}
