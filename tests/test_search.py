import pytest
import uuid

from app.services.search import SearchError, SearchService
from app.services.vector_store import VectorStore
from app.services.chunking import TextChunk


def unit_vector(index: int) -> list[float]:
    """Create a unit vector with one active dimension."""
    vector = [0.0] * 384
    vector[index] = 1.0
    return vector


class FakeEmbeddingService:
    """Deterministic embedding service for search tests."""

    def embed_query(self, query: str) -> list[float]:
        return unit_vector(0)


@pytest.fixture
def vector_store() -> VectorStore:
    collection_name = f"test-documents-{uuid.uuid4().hex}"

    store = VectorStore(
        collection_name=collection_name,
    )

    store.ensure_collection()

    store.upsert_chunks(
        document_id="document-a",
        document_name="relevant.pdf",
        chunks=[
            TextChunk(
                content="This content is relevant to the query.",
                chunk_index=0,
            )
        ],
        embeddings=[unit_vector(0)],
    )

    store.upsert_chunks(
        document_id="document-b",
        document_name="unrelated.pdf",
        chunks=[
            TextChunk(
                content="This content is unrelated.",
                chunk_index=0,
                )
        ],
        embeddings=[unit_vector(1)],
    )

    yield store

    if store.collection_exists():
        store.client.delete_collection(
            store.collection_name
        )


@pytest.fixture
def search_service(
    vector_store: VectorStore,
) -> SearchService:
    return SearchService(
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
        top_k=2,
    )


def test_search_returns_most_similar_result(
    search_service: SearchService,
):
    results = search_service.search(
        "How does this system work?"
    )

    assert len(results) == 2
    assert results[0].document == "relevant.pdf"
    assert results[0].content == (
        "This content is relevant to the query."
    )
    assert results[0].score > results[1].score


def test_search_respects_top_k(
    vector_store: VectorStore,
):
    service = SearchService(
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
        top_k=1,
    )

    results = service.search("test query")

    assert len(results) == 1
    assert results[0].document == "relevant.pdf"


def test_empty_query_is_rejected(
    search_service: SearchService,
):
    with pytest.raises(SearchError, match="empty"):
        search_service.search("")


def test_whitespace_query_is_rejected(
    search_service: SearchService,
):
    with pytest.raises(SearchError, match="empty"):
        search_service.search("   ")

class UnexpectedEmbeddingService:
    def embed_query(self, query: str):
        raise RuntimeError("Unexpected embedding failure.")

def test_unexpected_search_error_is_wrapped(
    vector_store: VectorStore,
):
    search_service = SearchService(
        embedding_service=UnexpectedEmbeddingService(),
        vector_store=vector_store,
    )

    with pytest.raises(
        SearchError,
        match="Search processing failed",
    ):
        search_service.search("How does semantic search work?")