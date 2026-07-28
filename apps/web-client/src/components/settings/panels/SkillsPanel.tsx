import type { SkillInfo } from "../../../lib/api";
import { SectionHeader } from "../controls/SectionHeader";
import type { PanelProps } from "../SettingsShell";

export function SkillsPanel({
  devMode,
  skills,
  onOpenSkillLab,
}: PanelProps & {
  skills: SkillInfo[];
  onOpenSkillLab: () => void;
}) {
  // Skills are files on disk, not preference keys, so there is no settings
  // group to reset and nothing that can read as "changed from defaults".
  return (
    <div className="space-y-6">
      <SectionHeader
        title="Skills"
        description="Type / in the composer to invoke one."
        modified={false}
      />

      <div>
        {/* `max-h-40` is carried over verbatim from the old modal, where the
            list shared one cramped column. It reads as a nested scroller now
            that the panel has its own height; left alone deliberately to keep
            this task behavior-neutral. */}
        <div className="space-y-1.5 max-h-40 overflow-y-auto custom-scrollbar p-1">
          {skills.length === 0 && (
            <p className="text-[11px] text-steel-muted px-2 py-1">
              No skills configured. Type <span className="font-mono">/</span> in the
              composer to invoke one.
            </p>
          )}
          {skills.map((skill) => (
            <div
              key={skill.id}
              className="flex flex-col px-3 py-2 rounded-lg bg-steel-ice border border-navy-700/20"
            >
              <span className="text-xs font-medium text-steel-dark">
                /{skill.id} · {skill.name}
              </span>
              <span className="text-[11px] text-steel-muted">{skill.description}</span>
            </div>
          ))}
        </div>
        {devMode && (
          <button
            onClick={onOpenSkillLab}
            className="mt-2 w-full text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2 transition"
          >
            Open Skill Lab
          </button>
        )}
      </div>
    </div>
  );
}
