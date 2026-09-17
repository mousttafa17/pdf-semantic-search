import pytest

from app.config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
)
from app.services.embeddings import (
    EmbeddingError,
    EmbeddingService,
)


@pytest.fixture(scope="module")
def embedding_service() -> EmbeddingService:
    return EmbeddingService()


def test_correct_model_is_configured():
    assert EMBEDDING_MODEL_NAME == "BAAI/bge-small-en-v1.5"


def test_model_dimension_is_configured_dimension(
    embedding_service: EmbeddingService,
):
    assert embedding_service.dimension == EMBEDDING_DIMENSION


def test_single_document_embedding_has_correct_dimension(
    embedding_service: EmbeddingService,
):
    embedding = embedding_service.embed_documents(
        [
            "Artificial intelligence enables systems to learn from data."
        ]
    )[0]

    assert len(embedding) == EMBEDDING_DIMENSION
    assert all(isinstance(value, float) for value in embedding)


def test_multiple_documents_return_multiple_embeddings(
    embedding_service: EmbeddingService,
):
    texts = [
        "Artificial intelligence enables systems to learn from data.",
        "Semantic search retrieves text using vector similarity.",
    ]

    embeddings = embedding_service.embed_documents(texts)

    assert len(embeddings) == 2
    assert all(
        len(embedding) == EMBEDDING_DIMENSION
        for embedding in embeddings
    )


def test_query_embedding_has_correct_dimension(
    embedding_service: EmbeddingService,
):
    embedding = embedding_service.embed_query(
        "How does semantic search work?"
    )

    assert len(embedding) == EMBEDDING_DIMENSION


def test_empty_document_text_is_rejected(
    embedding_service: EmbeddingService,
):
    with pytest.raises(EmbeddingError, match="empty"):
        embedding_service.embed_documents([""])


def test_empty_query_is_rejected(
    embedding_service: EmbeddingService,
):
    with pytest.raises(EmbeddingError, match="empty"):
        embedding_service.embed_query("   ")