from __future__ import annotations

import asyncio

from violet_speech.providers.mock_stt import MockSTTProvider


def test_mock_stt_returns_text_transcript() -> None:
    provider = MockSTTProvider()

    transcript = asyncio.run(provider.transcribe(" Halo Violet ", language="id"))

    assert transcript.text == "Halo Violet"
    assert transcript.language == "id"
    assert transcript.confidence == 1.0


def test_mock_stt_health() -> None:
    provider = MockSTTProvider()

    health = asyncio.run(provider.health())

    assert health.provider == "mock"
    assert health.status == "ok"

