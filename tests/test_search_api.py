from fastapi.testclient import TestClient

from app.api import search as search_api
from app.main import app
from app.services.search import SearchResult


class FakeSearchService:
    """Fake search service for API contract tests."""

    def search(self, query: str) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("Query cannot be empty.")

        return [
            SearchResult(
                document="sample.pdf",
                score=0.91,
                content="Semantic search retrieves relevant content.",
            )
        ]


client = TestClient(app)


def test_search_endpoint_returns_expected_shape(
    monkeypatch,
):
    monkeypatch.setattr(
        search_api,
        "search_service",
        FakeSearchService(),
    )

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


def test_search_endpoint_rejects_empty_query(
    monkeypatch,
):
    class EmptyQueryService:
        def search(self, query: str):
            from app.services.search import SearchError

            raise SearchError("Query cannot be empty.")

    monkeypatch.setattr(
        search_api,
        "search_service",
        EmptyQueryService(),
    )

    response = client.post(
        "/search/",
        json={"query": ""},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "Query cannot be empty."
    }