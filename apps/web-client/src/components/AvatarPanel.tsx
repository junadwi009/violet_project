import { Activity, Box, CircleAlert } from "lucide-react";
import {
  AvatarEmotion,
  AvatarState,
  emotionLabel,
  stateLabel,
} from "../lib/avatar";

type AvatarPanelProps = {
  state: AvatarState;
  emotion: AvatarEmotion;
  speechInputAvailable: boolean;
  speechOutputEnabled: boolean;
};

export function AvatarPanel({
  state,
  emotion,
  speechInputAvailable,
  speechOutputEnabled,
}: AvatarPanelProps) {
  return (
    <aside className="avatar-panel">
      <div className="avatar-header">
        <div>
          <h2>Violet</h2>
          <p>{stateLabel(state)}</p>
        </div>
        <div className={`avatar-dot ${state}`} aria-hidden="true" />
      </div>

      <div className={`avatar-stage ${state} ${emotion}`} aria-label="Avatar">
        <div className="avatar-halo" />
        <div className="avatar-figure">
          <div className="avatar-face">
            <div className="avatar-eye left" />
            <div className="avatar-eye right" />
            <div className="avatar-mouth" />
          </div>
        </div>
      </div>

      <div className="avatar-readout">
        <div>
          <Activity size={15} />
          <span>{emotionLabel(emotion)}</span>
        </div>
        <div>
          <Box size={15} />
          <span>Placeholder</span>
        </div>
        <div>
          <CircleAlert size={15} />
          <span>{speechInputAvailable ? "Mic ready" : "Mic unavailable"}</span>
        </div>
        <div>
          <Activity size={15} />
          <span>{speechOutputEnabled ? "Voice on" : "Voice off"}</span>
        </div>
      </div>
    </aside>
  );
}

