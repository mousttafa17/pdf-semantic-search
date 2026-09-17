from __future__ import annotations
from threading import Lock
from fastembed import TextEmbedding
from app.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL_NAME
class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


class EmbeddingService:
    """Generate embeddings for documents and search queries."""

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
    ) -> None:
        self.model_name = model_name
        self._model: TextEmbedding | None = None

        # Only protects the first-time model construction.
        # Actual embedding inference remains concurrent.
        self._model_lock = Lock()

    @property
    def model(self) -> TextEmbedding:
        """Lazily initialize the embedding model exactly once."""
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    self._model = TextEmbedding(
                        model_name=self.model_name
                    )

        return self._model

    @property
    def dimension(self) -> int:
        """Return the expected embedding dimension."""
        return EMBEDDING_DIMENSION

    def _validate_embedding_dimension(
        self,
        embedding: list[float],
    ) -> None:
        """Ensure an embedding matches the configured dimension."""
        if len(embedding) != self.dimension:
            raise EmbeddingError(
                f"Embedding dimension mismatch: expected "
                f"{self.dimension}, got {len(embedding)}."
            )

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings for document chunks."""
        if not texts:
            raise EmbeddingError(
                "Cannot generate embeddings for an empty document list."
            )

        if any(not text or not text.strip() for text in texts):
            raise EmbeddingError(
                "Cannot generate embeddings for empty document text."
            )

        try:
            prefixed_texts = [
                f"passage: {text.strip()}"
                for text in texts
            ]

            embeddings = self.model.embed(prefixed_texts)

            results = [
                embedding.tolist()
                for embedding in embeddings
            ]

            if len(results) != len(texts):
                raise EmbeddingError(
                    "Embedding model returned an unexpected number "
                    "of embeddings."
                )

            for embedding in results:
                self._validate_embedding_dimension(embedding)

            return results

        except EmbeddingError:
            raise

        except Exception as exc:
            raise EmbeddingError(
                "Failed to generate document embeddings."
            ) from exc

    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        """Generate an embedding for a search query."""
        if not query or not query.strip():
            raise EmbeddingError(
                "Search query cannot be empty."
            )

        try:
            prefixed_query = f"query: {query.strip()}"

            embeddings = self.model.embed([prefixed_query])

            embedding = next(embeddings).tolist()

            self._validate_embedding_dimension(embedding)

            return embedding

        except EmbeddingError:
            raise

        except Exception as exc:
            raise EmbeddingError(
                "Failed to generate query embedding."
            ) from exc