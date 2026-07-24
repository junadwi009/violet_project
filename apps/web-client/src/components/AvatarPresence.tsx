import { AvatarEmotion, AvatarState, emotionLabel, stateLabel } from "../lib/avatar";

type AvatarPresenceProps = {
  name: string;
  state: AvatarState;
  emotion: AvatarEmotion;
  visible: boolean;
};

/**
 * Floating portrait presence (top-right). Track 4 replaces the gradient orb below
 * with a three.js/VRM <canvas> without changing this component's props or layout.
 * Local-first: no external portrait image — a generated amethyst orb reacts to state.
 */
export function AvatarPresence({ name, state, emotion, visible }: AvatarPresenceProps) {
  const active = state === "listening" || state === "speaking";
  return (
    <div
      className={`fixed top-24 right-12 w-48 flex flex-col items-center text-center select-none z-20 transition-all duration-500 ease-in-out ${
        visible ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
    >
      <div className="relative mb-3 flex flex-col items-center">
        <div className="absolute inset-0 rounded-full glowing-avatar opacity-80 blur-2xl" />
        <div className="relative w-36 h-36 overflow-hidden z-10 soft-edge-avatar rounded-full">
          <div
            className={`w-full h-full rounded-full bg-[radial-gradient(circle_at_50%_35%,#c77dff_0%,#9d4edd_45%,#7b2cbf_75%,#5a189a_100%)] ${
              active ? "animate-pulse" : ""
            }`}
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-mono text-4xl font-semibold text-white/90 drop-shadow">
              V
            </span>
          </div>
        </div>
      </div>
      <h2 className="text-lg font-bold text-steel-dark tracking-wide">{name}</h2>
      <p className="text-[10px] text-steel font-semibold uppercase tracking-wider mt-0.5">
        {stateLabel(state)} · {emotionLabel(emotion)}
      </p>
    </div>
  );
}
