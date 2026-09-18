import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_search_service
from app.main import app

from app.services.embeddings import EmbeddingError
from app.services.search import (
    SearchResult,
    SearchValidationError,
)
from app.services.vector_store import VectorStoreError


class FakeSearchService:
    def search(self, query: str) -> list[SearchResult]:
        if not query.strip():
            raise SearchValidationError("Query cannot be empty.")

        return [
            SearchResult(
                document="sample.pdf",
                score=0.91,
                content="Semantic search retrieves relevant content.",
            )
        ]


@pytest.fixture
def client():
    app.dependency_overrides[get_search_service] = (
        lambda: FakeSearchService()
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_search_endpoint_returns_expected_shape(client):
    response = client.post(
        "/search/",
        json={"query": "How does semantic search work?"},
    )

    assert response.status_code == 200

    body = response.json()

    assert "results" in body
    assert isinstance(body["results"], list)

    result = body["results"][0]

    assert result["document"] == "sample.pdf"
    assert result["score"] == 0.91
    assert result["content"] == (
        "Semantic search retrieves relevant content."
    )


def test_search_endpoint_rejects_empty_query(client):
    response = client.post(
        "/search/",
        json={"query": ""},
    )

    assert response.status_code == 400

    assert response.json() == {
        "error": "Query cannot be empty."
    }

class EmbeddingFailureSearchService:
    def search(self, query: str) -> list[SearchResult]:
        raise EmbeddingError("Test embedding failure.")


class VectorStoreFailureSearchService:
    def search(self, query: str) -> list[SearchResult]:
        raise VectorStoreError("Test vector store failure.")


class UnexpectedFailureSearchService:
    def search(self, query: str) -> list[SearchResult]:
        raise RuntimeError("Test unexpected failure.")

def test_search_endpoint_returns_500_on_embedding_failure(client):
    app.dependency_overrides[get_search_service] = (
        lambda: EmbeddingFailureSearchService()
    )

    response = client.post(
        "/search/",
        json={"query": "How does semantic search work?"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": "Internal server error."
    }


def test_search_endpoint_returns_500_on_vector_store_failure(client):
    app.dependency_overrides[get_search_service] = (
        lambda: VectorStoreFailureSearchService()
    )

    response = client.post(
        "/search/",
        json={"query": "How does semantic search work?"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": "Internal server error."
    }


def test_search_endpoint_returns_500_on_unexpected_error(client):
    app.dependency_overrides[get_search_service] = (
        lambda: UnexpectedFailureSearchService()
    )

    response = client.post(
        "/search/",
        json={"query": "How does semantic search work?"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": "Internal server error."
    }

class EmptySearchService:
    def search(self, query: str) -> list[SearchResult]:
        return []

def test_search_rejects_whitespace_only_query(client):
    response = client.post(
        "/search/",
        json={"query": "     "},
    )

    assert response.status_code == 400

    assert response.json() == {
        "error": "Query cannot be empty."
    }

def test_search_rejects_malformed_json(client):
    response = client.post(
        "/search/",
        content='{"query":',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422

def test_search_rejects_non_string_query(client):
    response = client.post(
        "/search/",
        json={"query": 123},
    )

    assert response.status_code == 422
