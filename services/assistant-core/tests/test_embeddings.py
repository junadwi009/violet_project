from __future__ import annotations

import math

import pytest

from violet_assistant.config import load_settings
from violet_assistant.vector.embeddings.factory import create_embedder
from violet_assistant.vector.embeddings.mock_embedder import MockEmbedder


@pytest.mark.asyncio
async def test_mock_embedder_is_deterministic_and_normalized():
    emb = MockEmbedder(dim=256)
    a = (await emb.embed(["capital call notice"]))[0]
    b = (await emb.embed(["capital call notice"]))[0]
    assert a == b  # deterministic
    assert len(a) == 256
    norm = math.sqrt(sum(x * x for x in a))
    assert abs(norm - 1.0) < 1e-6  # L2-normalized


@pytest.mark.asyncio
async def test_mock_embedder_differs_for_different_text():
    emb = MockEmbedder(dim=256)
    a = (await emb.embed(["alpha"]))[0]
    b = (await emb.embed(["beta"]))[0]
    assert a != b


def test_factory_defaults_to_mock(tmp_path):
    assert create_embedder(load_settings(tmp_path)).name == "mock"
