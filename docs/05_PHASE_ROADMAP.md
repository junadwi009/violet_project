# Violet AI Phase Roadmap

## Phase 1 — Text Brain MVP

- Web chat UI
- Assistant Core API
- LLM adapter interface
- Mock provider
- Ollama/OpenAI-compatible provider
- Personality loader
- Sessions/messages DB
- Memory candidate extraction
- Memory review UI
- Tests and README

## Phase 2 — Voice

- STT adapter
- faster-whisper provider
- whisper.cpp provider
- VAD
- TTS adapter
- Piper/browser/mock TTS
- Audio playback UI

## Phase 3 — Avatar

- VRM loading
- Three.js/@pixiv/three-vrm
- idle/listening/thinking/speaking states
- simple lip-sync
- emotion mapping

## Phase 4 — Gesture

- MediaPipe Hands
- starter gestures
- gesture event API
- confidence threshold and cooldown
- local-only camera processing

## Phase 5 — Memory + Research

- approved long-term memory
- pgvector/search adapter
- SearXNG/paid search adapter
- source ranking
- prompt injection wrapper

## Phase 6 — Hybrid VPS

- Dockerize services
- Caddy WSS/HTTPS
- auth token
- monitoring
- backup
- local client connects to remote brain
