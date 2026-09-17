"""Unit test for thread-safe lazy embedding-model initialization."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import app.services.embeddings as embeddings_module
from app.services.embeddings import EmbeddingService


def test_embedding_model_is_initialized_once_under_concurrency(
    monkeypatch,
) -> None:
    """Concurrent first access should construct the model exactly once."""
    initialization_lock = Lock()
    initialization_count = 0

    class FakeTextEmbedding:
        def __init__(self, *, model_name: str) -> None:
            nonlocal initialization_count

            with initialization_lock:
                initialization_count += 1

    monkeypatch.setattr(
        embeddings_module,
        "TextEmbedding",
        FakeTextEmbedding,
    )

    service = EmbeddingService(model_name="test-model")

    def get_model():
        return service.model

    with ThreadPoolExecutor(max_workers=8) as executor:
        models = list(
            executor.map(
                lambda _: get_model(),
                range(32),
            )
        )

    assert initialization_count == 1
    assert all(model is models[0] for model in models)
