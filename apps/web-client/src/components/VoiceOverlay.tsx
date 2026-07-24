import { MicOff } from "lucide-react";

type VoiceOverlayProps = {
  open: boolean;
  name: string;
  onStop: () => void;
};

/**
 * Full-screen voice session overlay (Track 5/6 wire real STT/TTS here later;
 * today it fronts the browser Web Speech capture driven by App).
 */
export function VoiceOverlay({ open, name, onStop }: VoiceOverlayProps) {
  return (
    <div
      className={`absolute inset-0 z-30 flex flex-col items-center justify-center bg-gradient-to-b from-white via-navy-950 to-navy-900 transition-all duration-500 ease-in-out ${
        open ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
    >
      <div className="flex flex-col items-center text-center max-w-sm px-6">
        <div className="relative mb-6 flex flex-col items-center">
          <div className="absolute inset-0 rounded-full glowing-avatar opacity-75 blur-3xl" />
          <div className="relative w-52 h-52 overflow-hidden z-10 soft-edge-avatar rounded-full">
            <div className="w-full h-full rounded-full bg-[radial-gradient(circle_at_50%_35%,#c77dff_0%,#9d4edd_45%,#7b2cbf_75%,#5a189a_100%)] animate-pulse" />
          </div>
        </div>

        <h2 className="text-3xl font-extrabold text-steel-dark tracking-wide">{name}</h2>
        <p className="text-xs text-steel-highlight font-bold uppercase tracking-widest mt-1.5">
          Voice session
        </p>

        <div className="flex items-end justify-center gap-1.5 h-12 my-8">
          <span className="w-1 bg-steel-highlight rounded-full animate-bounce h-6" style={{ animationDuration: "0.8s" }} />
          <span className="w-1 bg-steel-light rounded-full animate-bounce h-10" style={{ animationDuration: "1.1s", animationDelay: "0.15s" }} />
          <span className="w-1 bg-steel-highlight rounded-full animate-bounce h-8" style={{ animationDuration: "0.9s", animationDelay: "0.3s" }} />
          <span className="w-1 bg-steel-light rounded-full animate-bounce h-12" style={{ animationDuration: "1.2s", animationDelay: "0.45s" }} />
          <span className="w-1 bg-steel-highlight rounded-full animate-bounce h-5" style={{ animationDuration: "0.7s", animationDelay: "0.1s" }} />
        </div>

        <div className="flex flex-col items-center gap-2 mt-4">
          <button
            onClick={onStop}
            className="w-16 h-16 bg-red-600 hover:bg-red-700 text-white rounded-full flex items-center justify-center shadow-lg transition duration-200 active:scale-95"
            title="Stop voice session"
          >
            <MicOff size={22} />
          </button>
          <span className="text-[11px] text-steel-highlight font-bold uppercase tracking-widest mt-1">
            Pause Session
          </span>
        </div>
      </div>
    </div>
  );
}
