import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_search_service
from app.main import app
from app.services.search import SearchError, SearchResult


class FakeSearchService:
    def search(self, query: str) -> list[SearchResult]:
        if not query.strip():
            raise SearchError("Query cannot be empty.")

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