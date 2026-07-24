import { FormEvent } from "react";
import { Mic, Square, ArrowUp, Volume2, VolumeX, ChevronDown } from "lucide-react";

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
  } = props;

  return (
    <form
      onSubmit={onSubmit}
      className={variant === "footer" ? "relative w-full lg:w-3/5 ml-0 mr-auto lg:ml-12" : "relative w-full"}
    >
      <div className="relative flex items-center bg-white rounded-full shadow-lg pl-4 pr-3 py-3 transition focus-within:ring-2 focus-within:ring-steel-highlight/20 border border-navy-700/30">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete="off"
          placeholder={`Ask ${assistantName}…`}
          className="flex-1 bg-transparent text-steel-dark placeholder-steel/50 font-medium px-3 text-sm focus:outline-none py-1 w-full"
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
            {isListening ? <Square size={16} className="text-red-500" /> : <Mic size={17} />}
          </button>

          <button
            type="submit"
            disabled={!canSend}
            className="w-8 h-8 rounded-full bg-steel-dark hover:bg-black text-white flex items-center justify-center transition shadow-md active:scale-95 disabled:opacity-40"
            title="Send"
          >
            <ArrowUp size={15} />
          </button>
        </div>
      </div>
      {variant === "footer" && (
        <div className="text-left text-[10px] text-steel/60 mt-2.5 pl-6">
          {assistantName} can make mistakes. Memory is saved only after you approve it.
        </div>
      )}
    </form>
  );
}
