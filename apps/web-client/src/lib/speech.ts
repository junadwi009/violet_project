type SpeechRecognitionConstructor = new () => SpeechRecognition;

type SpeechRecognitionResultAlternative = {
  transcript: string;
  confidence: number;
};

type SpeechRecognitionResult = {
  readonly length: number;
  item(index: number): SpeechRecognitionResultAlternative;
  [index: number]: SpeechRecognitionResultAlternative;
  isFinal: boolean;
};

type SpeechRecognitionResultList = {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
};

type SpeechRecognitionEvent = Event & {
  results: SpeechRecognitionResultList;
};

type SpeechRecognitionErrorEvent = Event & {
  error: string;
};

type SpeechRecognition = EventTarget & {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
};

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

export function canRecognizeSpeech(): boolean {
  return Boolean(window.SpeechRecognition ?? window.webkitSpeechRecognition);
}

export function canSpeak(): boolean {
  return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

export type VoiceSettings = {
  lang: string;
  voiceName: string;
  rate: number;
  pitch: number;
};

export const DEFAULT_VOICE: VoiceSettings = {
  lang: "id-ID",
  voiceName: "",
  rate: 1,
  pitch: 1,
};

/** Browser voice lists are per-browser and per-OS, and populate asynchronously. */
export function listVoices(): SpeechSynthesisVoice[] {
  if (!canSpeak()) return [];
  return window.speechSynthesis.getVoices();
}

export function onVoicesChanged(callback: () => void): () => void {
  if (!canSpeak()) return () => {};
  window.speechSynthesis.addEventListener("voiceschanged", callback);
  return () =>
    window.speechSynthesis.removeEventListener("voiceschanged", callback);
}

export function createSpeechRecognizer(
  onFinalText: (text: string) => void,
  onError: (message: string) => void,
  onEnd: () => void,
  voice: VoiceSettings = DEFAULT_VOICE,
): SpeechRecognition | null {
  const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
  if (!Recognition) {
    return null;
  }

  const recognition = new Recognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = voice.lang;
  recognition.onresult = (event: SpeechRecognitionEvent) => {
    const result = event.results.item(0);
    const alternative = result.item(0);
    onFinalText(alternative.transcript.trim());
  };
  recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
    onError(event.error);
  };
  recognition.onend = onEnd;
  return recognition;
}

export function speakText(
  text: string,
  voice: VoiceSettings = DEFAULT_VOICE,
  onEnd?: () => void,
): void {
  if (!canSpeak()) {
    onEnd?.();
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = voice.lang;
  utterance.rate = voice.rate;
  utterance.pitch = voice.pitch;
  if (voice.voiceName) {
    // A stored name may not exist in this browser; fall back silently.
    const match = listVoices().find((item) => item.name === voice.voiceName);
    if (match) utterance.voice = match;
  }
  utterance.onend = () => onEnd?.();
  utterance.onerror = () => onEnd?.();
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking(): void {
  if (canSpeak()) {
    window.speechSynthesis.cancel();
  }
}
