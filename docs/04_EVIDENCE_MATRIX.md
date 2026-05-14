# Evidence Matrix — Violet AI

Verified on 2026-05-14.

| Area | Recommended choice | Main evidence |
|---|---|---|
| Gesture | MediaPipe Hands/Gesture Recognizer | Google AI Edge docs confirm realtime gesture recognition and hand landmarks. |
| STT | faster-whisper + whisper.cpp fallback | faster-whisper uses CTranslate2 and claims faster/lower-memory Whisper inference; whisper.cpp is C/C++ and supports local CPU/GPU inference. |
| Wake word | openWakeWord | Open-source wake-word library with pretrained models and custom training. |
| TTS fast mode | Piper | Fast local neural TTS; check current license path before commercial deployment. |
| TTS clone mode | XTTS-v2/OpenVoice/Fish Speech adapters | XTTS supports short-clip cloning but has license caveats; OpenVoice V2 is MIT; Fish Speech supports short-reference cloning with license checks needed. |
| Avatar | VRM + @pixiv/three-vrm | Official Three.js VRM library. |
| Unity option | UniVRM | Standard Unity implementation for VRM. |
| Lip-sync | Amplitude first, Wawa/wLipSync later | Wawa Lipsync supports realtime web lip sync; Rhubarb is better for offline/batch. |
| Memory | DIY first, then Mem0/Letta optional | Mem0/Letta are memory frameworks; pgvector stores vectors inside Postgres. |
| Research | SearXNG or paid search API adapter | SearXNG is self-hosted metasearch without tracking/profiling. |
| Runtime | OpenAI-compatible adapter | Ollama, LM Studio, and vLLM support OpenAI-compatible APIs; llama.cpp supports local inference. |
| Deployment | Docker Compose + Caddy + Uptime Kuma | Compose for multi-container apps; Caddy automatic HTTPS; Uptime Kuma monitoring. |
| Security | OWASP LLM Top 10 controls | OWASP lists prompt injection as LLM01. |
