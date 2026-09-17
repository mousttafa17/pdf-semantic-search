from dataclasses import dataclass

from app.config import SEARCH_TOP_K
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStore


class SearchError(Exception):
    """Raised when semantic search fails."""


@dataclass(frozen=True)
class SearchResult:
    """A semantic-search result."""

    document: str
    score: float
    content: str


class SearchService:
    """Coordinates query embedding and vector similarity search."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        top_k: int = SEARCH_TOP_K,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.top_k = top_k

    def search(self, query: str) -> list[SearchResult]:
        """
        Search for document chunks semantically related to the query.
        """
        if not query or not query.strip():
            raise SearchError("Query cannot be empty.")

        try:
            query_embedding = self.embedding_service.embed_query(
                query.strip()
            )

            points = self.vector_store.search(
                query_embedding=query_embedding,
                limit=self.top_k,
            )

        except Exception as exc:
            if isinstance(exc, SearchError):
                raise

            raise SearchError(
                "Search processing failed."
            ) from exc

        results: list[SearchResult] = []

        for point in points:
            payload = point.payload or {}

            document = payload.get("document")
            content = payload.get("content")

            if not document or not content:
                continue

            results.append(
                SearchResult(
                    document=document,
                    score=float(point.score),
                    content=content,
                )
            )

        return results