import uuid

import pytest
from qdrant_client.models import PointStruct

from app.config import EMBEDDING_DIMENSION
from app.services.vector_store import (
    VectorStore,
    VectorStoreError,
)


def fake_embedding(seed: float) -> list[float]:
    """Create a deterministic test vector of the correct dimension."""
    return [seed] * EMBEDDING_DIMENSION


@pytest.fixture
def vector_store() -> VectorStore:
    store = VectorStore()

    if store.collection_exists():
        store.client.delete_collection(store.collection_name)

    store.ensure_collection()

    return store


def test_collection_exists(vector_store: VectorStore):
    assert vector_store.collection_exists()


def test_upsert_chunks_stores_points(vector_store: VectorStore):
    document_id = str(uuid.uuid4())

    chunks = [
        "Artificial intelligence enables systems to learn from data.",
        "Semantic search uses embeddings to compare meaning.",
    ]

    embeddings = [
        fake_embedding(0.1),
        fake_embedding(0.2),
    ]

    stored_count = vector_store.upsert_chunks(
        document_id=document_id,
        document_name="sample.pdf",
        chunks=chunks,
        embeddings=embeddings,
    )

    assert stored_count == 2

    points = vector_store.client.scroll(
        collection_name=vector_store.collection_name,
        limit=10,
        with_payload=True,
        with_vectors=True,
    )[0]

    assert len(points) == 2

    payloads = [point.payload for point in points]

    assert any(
        payload["document"] == "sample.pdf"
        and payload["chunk_index"] == 0
        and payload["content"] == chunks[0]
        for payload in payloads
    )

    assert any(
        payload["document"] == "sample.pdf"
        and payload["chunk_index"] == 1
        and payload["content"] == chunks[1]
        for payload in payloads
    )


def test_reingestion_updates_existing_points(
    vector_store: VectorStore,
):
    document_id = str(uuid.uuid4())

    original_chunks = [
        "Original content.",
    ]

    updated_chunks = [
        "Updated content.",
    ]

    embedding = fake_embedding(0.5)

    vector_store.upsert_chunks(
        document_id=document_id,
        document_name="sample.pdf",
        chunks=original_chunks,
        embeddings=[embedding],
    )

    vector_store.upsert_chunks(
        document_id=document_id,
        document_name="sample.pdf",
        chunks=updated_chunks,
        embeddings=[embedding],
    )

    points = vector_store.client.scroll(
        collection_name=vector_store.collection_name,
        limit=10,
        with_payload=True,
    )[0]

    assert len(points) == 1
    assert points[0].payload["content"] == "Updated content."


def test_mismatched_chunk_and_embedding_counts_are_rejected(
    vector_store: VectorStore,
):
    with pytest.raises(
        VectorStoreError,
        match="must match",
    ):
        vector_store.upsert_chunks(
            document_id=str(uuid.uuid4()),
            document_name="sample.pdf",
            chunks=["one", "two"],
            embeddings=[fake_embedding(0.1)],
        )


def test_wrong_embedding_dimension_is_rejected(
    vector_store: VectorStore,
):
    with pytest.raises(
        VectorStoreError,
        match="dimension mismatch",
    ):
        vector_store.upsert_chunks(
            document_id=str(uuid.uuid4()),
            document_name="sample.pdf",
            chunks=["some text"],
            embeddings=[[0.1, 0.2, 0.3]],
        )


def test_empty_chunks_returns_zero(
    vector_store: VectorStore,
):
    count = vector_store.upsert_chunks(
        document_id=str(uuid.uuid4()),
        document_name="sample.pdf",
        chunks=[],
        embeddings=[],
    )

    assert count == 0