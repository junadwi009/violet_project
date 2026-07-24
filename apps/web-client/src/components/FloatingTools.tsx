import { Database, SlidersHorizontal, HelpCircle } from "lucide-react";

type FloatingToolsProps = {
  visible: boolean;
  pendingCount: number;
  onToggleMemory: () => void;
  onOpenSettings: () => void;
  onOpenHelp: () => void;
};

export function FloatingTools({
  visible,
  pendingCount,
  onToggleMemory,
  onOpenSettings,
  onOpenHelp,
}: FloatingToolsProps) {
  if (!visible) return null;
  return (
    <>
      <div className="fixed right-12 bottom-36 flex flex-col items-center glass-panel py-4 px-2.5 rounded-[2rem] shadow-lg z-20 gap-5 w-12">
        <button
          onClick={onToggleMemory}
          className="w-8 h-8 rounded-full flex items-center justify-center text-steel hover:text-steel-dark hover:bg-steel-ice transition relative group"
          title="Memory"
        >
          <Database size={16} />
          {pendingCount > 0 && (
            <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-steel-highlight text-white text-[9px] font-bold flex items-center justify-center">
              {pendingCount}
            </span>
          )}
          <span className="absolute right-12 scale-0 group-hover:scale-100 bg-steel-dark text-xs px-2.5 py-1 rounded-md text-white transition-all whitespace-nowrap shadow-md">
            Memory
          </span>
        </button>

        <div className="w-6 h-px bg-navy-700/20" />

        <button
          onClick={onOpenSettings}
          className="w-8 h-8 rounded-full flex items-center justify-center text-steel hover:text-steel-dark hover:bg-steel-ice transition relative group"
          title="Settings"
        >
          <SlidersHorizontal size={16} />
          <span className="absolute right-12 scale-0 group-hover:scale-100 bg-steel-dark text-xs px-2.5 py-1 rounded-md text-white transition-all whitespace-nowrap shadow-md">
            Settings
          </span>
        </button>
      </div>

      <div className="fixed right-12 bottom-12 z-20">
        <button
          onClick={onOpenHelp}
          className="w-10 h-10 rounded-full bg-white hover:bg-steel-ice border border-navy-700/20 flex items-center justify-center text-steel hover:text-steel-dark transition shadow-md"
          title="About"
        >
          <HelpCircle size={18} />
        </button>
      </div>
    </>
  );
}
