from functools import lru_cache

from app.services.embeddings import EmbeddingService
from app.services.ingestion import IngestionService
from app.services.search import SearchService
from app.services.vector_store import VectorStore


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Return the shared embedding service."""
    return EmbeddingService()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    """Return the shared vector-store service."""
    return VectorStore()


@lru_cache(maxsize=1)
def get_ingestion_service() -> IngestionService:
    """Return the shared ingestion service."""
    return IngestionService(
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store(),
    )


@lru_cache(maxsize=1)
def get_search_service() -> SearchService:
    """Return the shared search service."""
    return SearchService(
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store(),
    )