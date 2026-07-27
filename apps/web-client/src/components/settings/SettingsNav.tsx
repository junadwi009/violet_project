import type { ReactNode } from "react";

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

  return (
    <nav
      role="tablist"
      aria-orientation="vertical"
      aria-label="Settings sections"
      className="w-44 shrink-0 border-r border-navy-700/20 p-3 space-y-0.5 overflow-y-auto custom-scrollbar"
      onKeyDown={(event) => {
        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
        event.preventDefault();
        const index = visible.findIndex((item) => item.id === active);
        const delta = event.key === "ArrowDown" ? 1 : -1;
        const next = (index + delta + visible.length) % visible.length;
        onSelect(visible[next].id);
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
            aria-selected={item.id === active}
            tabIndex={item.id === active ? 0 : -1}
            onClick={() => onSelect(item.id)}
            className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs font-medium transition text-left ${
              item.id === active
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
