import { FormEvent, useRef } from "react";
import {
  Mic,
  Square,
  ArrowUp,
  Volume2,
  VolumeX,
  ChevronDown,
  Paperclip,
  FileText,
  Loader2,
  Globe,
  Sparkles,
  X,
} from "lucide-react";
import { SkillPalette } from "./SkillPalette";

type Attachment = { filename: string; ocr: boolean };
type ActiveSkill = { id: string; name: string };

type ComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  canSend: boolean;
  speechInputAvailable: boolean;
  isListening: boolean;
  onToggleListen: () => void;
  speechOutputAvailable: boolean;
  speechOutputEnabled: boolean;
  onToggleSpeechOutput: () => void;
  providerLabel: string;
  onOpenSettings: () => void;
  assistantName: string;
  variant: "footer" | "hero";
  onAttach: (file: File) => void;
  attaching: boolean;
  attachment: Attachment | null;
  onRemoveAttachment: () => void;
  activeSkill: ActiveSkill | null;
  onPickSkill: (skill: ActiveSkill | null) => void;
  webSearchAvailable: boolean;
  webSearchOn: boolean;
  onToggleWebSearch: () => void;
};

export function Composer(props: ComposerProps) {
  const {
    value,
    onChange,
    onSubmit,
    canSend,
    speechInputAvailable,
    isListening,
    onToggleListen,
    speechOutputAvailable,
    speechOutputEnabled,
    onToggleSpeechOutput,
    providerLabel,
    onOpenSettings,
    assistantName,
    variant,
    onAttach,
    attaching,
    attachment,
    onRemoveAttachment,
    activeSkill,
    onPickSkill,
    webSearchAvailable,
    webSearchOn,
    onToggleWebSearch,
  } = props;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const slashQuery =
    !activeSkill && value.startsWith("/") ? value.slice(1) : null;

  return (
    <form
      onSubmit={onSubmit}
      className={variant === "footer" ? "relative w-full lg:w-3/5 ml-0 mr-auto lg:ml-12" : "relative w-full"}
    >
      {slashQuery !== null && (
        <SkillPalette
          query={slashQuery}
          onPick={(skill) => {
            onPickSkill({ id: skill.id, name: skill.name });
            onChange("");
          }}
          onClose={() => onChange("")}
        />
      )}
      {activeSkill && (
        <div className="mb-2 mr-2 inline-flex items-center gap-2 bg-steel-highlight/10 border border-steel-highlight/30 rounded-full pl-3 pr-1.5 py-1 text-xs text-steel-highlight max-w-full">
          <Sparkles size={12} className="shrink-0" />
          <span className="truncate max-w-[180px]">/{activeSkill.id} · {activeSkill.name}</span>
          <button
            type="button"
            onClick={() => onPickSkill(null)}
            className="w-5 h-5 rounded-full flex items-center justify-center hover:bg-navy-800/70"
            title="Remove skill"
          >
            <X size={12} />
          </button>
        </div>
      )}
      {attachment && (
        <div className="mb-2 inline-flex items-center gap-2 bg-steel-ice border border-navy-700/20 rounded-full pl-3 pr-1.5 py-1 text-xs text-steel-dark max-w-full">
          <FileText size={13} className="text-steel-highlight shrink-0" />
          <span className="truncate max-w-[220px]">{attachment.filename}</span>
          {attachment.ocr && (
            <span className="text-[9px] uppercase tracking-wider text-steel-muted">OCR</span>
          )}
          <button
            type="button"
            onClick={onRemoveAttachment}
            className="w-5 h-5 rounded-full flex items-center justify-center text-steel hover:bg-navy-800/70"
            title="Remove attachment"
          >
            <X size={12} />
          </button>
        </div>
      )}
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept=".csv,.tsv,.xlsx,.xlsm,.pdf,.docx,.txt,.md,.json,.png,.jpg,.jpeg,.webp,.gif,.bmp"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onAttach(file);
          e.target.value = "";
        }}
      />
      <div className="relative flex items-center bg-navy-800 rounded-full shadow-lg pl-3 pr-3 py-3 transition focus-within:ring-2 focus-within:ring-steel-highlight/20 border border-navy-700/30">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={attaching}
          className="w-8 h-8 rounded-full flex items-center justify-center text-steel hover:bg-steel-ice transition shrink-0 disabled:opacity-50"
          title="Attach a file (CSV, PDF, DOCX, image → OCR)"
        >
          {attaching ? <Loader2 size={17} className="animate-spin" /> : <Paperclip size={17} />}
        </button>
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape" && slashQuery !== null) {
              e.preventDefault();
              onChange("");
            }
          }}
          autoComplete="off"
          placeholder={
            activeSkill ? `Prompt for /${activeSkill.id}…` : `Ask ${assistantName}…`
          }
          className="flex-1 bg-transparent text-steel-dark placeholder-steel-muted font-medium px-3 text-sm focus:outline-none py-1 w-full"
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenSettings}
            className="flex items-center gap-1 bg-steel-ice hover:bg-steel/10 px-2.5 py-1.5 rounded-full border border-navy-700/10 transition text-xs text-steel font-medium"
            title="Change AI engine"
          >
            <span>{providerLabel}</span>
            <ChevronDown size={11} />
          </button>

          {webSearchAvailable && (
            <button
              type="button"
              onClick={onToggleWebSearch}
              className={`w-8 h-8 rounded-full flex items-center justify-center transition ${
                webSearchOn
                  ? "bg-steel-highlight/15 text-steel-highlight"
                  : "text-steel hover:bg-steel-ice"
              }`}
              title={webSearchOn ? "Web search on" : "Search the web"}
            >
              <Globe size={17} />
            </button>
          )}

          {speechOutputAvailable && (
            <button
              type="button"
              onClick={onToggleSpeechOutput}
              className="w-8 h-8 rounded-full flex items-center justify-center text-steel hover:bg-steel-ice transition"
              title={speechOutputEnabled ? "Disable speech output" : "Enable speech output"}
            >
              {speechOutputEnabled ? <Volume2 size={17} /> : <VolumeX size={17} />}
            </button>
          )}

          <button
            type="button"
            onClick={onToggleListen}
            disabled={!speechInputAvailable}
            className="w-8 h-8 rounded-full flex items-center justify-center text-steel hover:bg-steel-ice transition disabled:opacity-40 disabled:hover:bg-transparent"
            title={isListening ? "Stop listening" : "Start voice input"}
          >
            {isListening ? <Square size={16} className="text-[color:var(--color-danger)]" /> : <Mic size={17} />}
          </button>

          <button
            type="submit"
            disabled={!canSend}
            className="w-8 h-8 rounded-full bg-steel-dark hover:opacity-90 text-navy-950 flex items-center justify-center transition shadow-md active:scale-95 disabled:opacity-40"
            title="Send"
          >
            <ArrowUp size={15} />
          </button>
        </div>
      </div>
      {variant === "footer" && (
        <div className="text-left text-[10px] text-steel-muted mt-2.5 pl-6">
          {assistantName} can make mistakes. Memory is saved only after you approve it.
        </div>
      )}
    </form>
  );
}
