from __future__ import annotations

import asyncio

from violet_tts.providers.mock_tts import MockTTSProvider


def test_mock_tts_returns_text_result_without_audio() -> None:
    provider = MockTTSProvider()

    result = asyncio.run(
        provider.synthesize("Halo Violet", voice="default", language="id")
    )

    assert result.text == "Halo Violet"
    assert result.voice == "default"
    assert result.language == "id"
    assert result.audio_base64 is None


def test_mock_tts_health() -> None:
    provider = MockTTSProvider()

    health = asyncio.run(provider.health())

    assert health.provider == "mock"
    assert health.status == "ok"

