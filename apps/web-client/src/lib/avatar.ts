export type AvatarState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "confirming"
  | "warning"
  | "error";

export type AvatarEmotion =
  | "neutral"
  | "focused"
  | "calm"
  | "happy"
  | "concerned";

export function normalizeEmotion(emotion: string): AvatarEmotion {
  const normalized = emotion.trim().toLowerCase();
  if (
    normalized === "focused" ||
    normalized === "calm" ||
    normalized === "happy" ||
    normalized === "concerned"
  ) {
    return normalized;
  }
  return "neutral";
}

export function stateLabel(state: AvatarState): string {
  const labels: Record<AvatarState, string> = {
    idle: "Idle",
    listening: "Listening",
    thinking: "Thinking",
    speaking: "Speaking",
    confirming: "Confirming",
    warning: "Review",
    error: "Error",
  };
  return labels[state];
}

export function emotionLabel(emotion: AvatarEmotion): string {
  const labels: Record<AvatarEmotion, string> = {
    neutral: "Neutral",
    focused: "Focused",
    calm: "Calm",
    happy: "Warm",
    concerned: "Concerned",
  };
  return labels[emotion];
}

