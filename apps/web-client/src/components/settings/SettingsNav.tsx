import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { settingsPanelDomId, settingsTabDomId } from "./ids";

export type NavItem = {
  id: string;
  label: string;
  icon: ReactNode;
  devOnly?: boolean;
};

export function SettingsNav({
  items,
  active,
  onSelect,
  devMode,
}: {
  items: NavItem[];
  active: string;
  onSelect: (id: string) => void;
  devMode: boolean;
}) {
  const visible = items.filter((item) => devMode || !item.devOnly);
  const firstDevIndex = visible.findIndex((item) => item.devOnly);
  const activeIndex = visible.findIndex((item) => item.id === active);

  // Keyboard nav must move real DOM focus, not just `aria-selected`: assistive
  // tech announces on focus change, and roving tabindex parks `tabindex="-1"`
  // on whatever the browser is still focused on otherwise.
  const tabRefs = useRef(new Map<string, HTMLButtonElement>());

  // `onSelect` is typically an inline arrow from the caller, so it is held in a
  // ref rather than depended on — otherwise the recovery effect below would
  // re-run on every parent render.
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  });

  // If `active` points at a tab that is no longer visible (the usual case: a
  // `devOnly` tab selected, then `devMode` switched off) nothing carries
  // `aria-selected="true"`, no tab is tabbable, and the shell's open-focus
  // query finds nothing. Hand selection back to the first visible tab.
  const visibleKey = visible.map((item) => item.id).join("|");
  useEffect(() => {
    if (visible.length === 0) return;
    if (activeIndex >= 0) return;
    // Removing the focused tab drops focus to <body>; WCAG 2.4.3 wants it kept
    // somewhere sensible. Only reclaim it if nothing else has taken it.
    const focusWasLost =
      document.activeElement === null ||
      document.activeElement === document.body;
    onSelectRef.current(visible[0].id);
    if (focusWasLost) tabRefs.current.get(visible[0].id)?.focus();
    // `visibleKey` stands in for `visible`, which is a fresh array each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleKey, activeIndex]);

  // Until the parent applies that correction, keep exactly one tab tabbable so
  // the dialog never contains a tablist the keyboard cannot enter.
  const tabbableIndex = activeIndex >= 0 ? activeIndex : 0;

  function moveTo(index: number) {
    const item = visible[index];
    if (!item) return;
    onSelect(item.id);
    tabRefs.current.get(item.id)?.focus();
  }

  return (
    <nav
      role="tablist"
      aria-orientation="vertical"
      aria-label="Settings sections"
      className="w-44 shrink-0 border-r border-navy-700/20 p-3 space-y-0.5 overflow-y-auto custom-scrollbar"
      onKeyDown={(event) => {
        if (visible.length === 0) return;
        const current = tabbableIndex;
        let next: number;
        switch (event.key) {
          case "ArrowDown":
            next = (current + 1) % visible.length;
            break;
          case "ArrowUp":
            next = (current - 1 + visible.length) % visible.length;
            break;
          case "Home":
            next = 0;
            break;
          case "End":
            next = visible.length - 1;
            break;
          default:
            return;
        }
        event.preventDefault();
        moveTo(next);
      }}
    >
      {visible.map((item, index) => (
        <div key={item.id}>
          {index === firstDevIndex && firstDevIndex > 0 && (
            <div className="flex items-center gap-2 px-2 pt-3 pb-1.5">
              <span className="text-[10px] uppercase tracking-wider text-steel/50">
                dev
              </span>
              <span className="flex-1 h-px bg-navy-700/20" />
            </div>
          )}
          <button
            type="button"
            role="tab"
            id={settingsTabDomId(item.id)}
            aria-controls={settingsPanelDomId(item.id)}
            aria-selected={index === tabbableIndex}
            tabIndex={index === tabbableIndex ? 0 : -1}
            ref={(node) => {
              if (node) tabRefs.current.set(item.id, node);
              else tabRefs.current.delete(item.id);
            }}
            onClick={() => onSelect(item.id)}
            className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs font-medium transition text-left ${
              index === tabbableIndex
                ? "bg-steel-highlight/10 text-steel-highlight"
                : "text-steel hover:bg-steel-ice hover:text-steel-dark"
            }`}
          >
            {item.icon}
            {item.label}
          </button>
        </div>
      ))}
    </nav>
  );
}
