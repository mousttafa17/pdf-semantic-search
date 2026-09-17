import logging

from dataclasses import dataclass
from time import perf_counter

from app.config import SEARCH_TOP_K
from app.services.embeddings import EmbeddingService, EmbeddingError
from app.services.vector_store import VectorStore, VectorStoreError

logger = logging.getLogger(__name__)


class SearchError(Exception):
    """Base class for semantic-search errors."""


class SearchValidationError(SearchError):
    """Raised when the search request is invalid."""


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
        if not query or not query.strip():
            logger.warning("Search rejected reason=empty_query")
            raise SearchValidationError("Search query cannot be empty.")
    
        start_time = perf_counter()
        query_length = len(query.strip())
    
        logger.info(
            "Search started query_length=%d top_k=%d",
            query_length,
            self.top_k,
        )
    
        try:
            query_embedding = self.embedding_service.embed_query(query)
    
            points = self.vector_store.search(
                query_embedding=query_embedding,
                limit=self.top_k,
            )
    
            results = []
    
            for point in points:
                payload = point.payload or {}
    
                results.append(
                    SearchResult(
                        document=payload.get("document", ""),
                        score=float(point.score),
                        content=payload.get("content", ""),
                    )
                )
    
            duration_ms = (perf_counter() - start_time) * 1000
    
            logger.info(
                "Search completed results=%d duration_ms=%.2f",
                len(results),
                duration_ms,
            )
    
            return results
    
        except (EmbeddingError, VectorStoreError):
            logger.exception(
                "Search infrastructure failure query_length=%d",
                query_length,
            )
            raise
        
        except Exception as exc:
            logger.exception(
                "Unexpected search failure query_length=%d",
                query_length,
            )
            raise SearchError("Search processing failed.") from None