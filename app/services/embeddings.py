from functools import lru_cache

from fastembed import TextEmbedding

from app.config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
)


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


class EmbeddingService:
    """Generates embeddings for document passages and search queries."""

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
    ) -> None:
        self.model_name = model_name
        self._model: TextEmbedding | None = None

    @property
    def model(self) -> TextEmbedding:
        """Load the embedding model lazily and reuse it."""
        if self._model is None:
            try:
                self._model = TextEmbedding(
                    model_name=self.model_name,
                )
            except Exception as exc:
                raise EmbeddingError(
                    f"Failed to load embedding model: {self.model_name}"
                ) from exc

        return self._model

    @property
    def dimension(self) -> int:
        """Return the configured embedding dimension."""
        # FastEmbed's supported model metadata can be used to determine
        # the actual dimension; we also verify the generated vector.
        return EMBEDDING_DIMENSION

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Generate embeddings for document passages.

        BGE retrieval models benefit from the `passage:` prefix.
        """
        self._validate_texts(texts)

        prefixed_texts = [
            f"passage: {text}" for text in texts
        ]

        try:
            embeddings = self.model.embed(prefixed_texts)

            result = [
                embedding.tolist()
                for embedding in embeddings
            ]
        except Exception as exc:
            raise EmbeddingError(
                "Failed to generate document embeddings."
            ) from exc

        self._validate_embedding_dimensions(result)

        return result

    def embed_query(self, query: str) -> list[float]:
        """
        Generate an embedding for a search query.

        BGE retrieval models benefit from the `query:` prefix.
        """
        if not query or not query.strip():
            raise EmbeddingError("Cannot embed an empty query.")

        try:
            embeddings = self.model.embed(
                [f"query: {query.strip()}"]
            )

            result = next(embeddings).tolist()
        except Exception as exc:
            raise EmbeddingError(
                "Failed to generate query embedding."
            ) from exc

        self._validate_embedding_dimensions([result])

        return result

    def _validate_texts(self, texts: list[str]) -> None:
        if not texts:
            raise EmbeddingError(
                "Cannot embed an empty list of texts."
            )

        if any(not text or not text.strip() for text in texts):
            raise EmbeddingError(
                "Cannot embed empty or whitespace-only text."
            )

    @staticmethod
    def _validate_embedding_dimensions(
        embeddings: list[list[float]],
    ) -> None:
        for embedding in embeddings:
            if len(embedding) != EMBEDDING_DIMENSION:
                raise EmbeddingError(
                    "Embedding dimension mismatch: "
                    f"expected {EMBEDDING_DIMENSION}, "
                    f"got {len(embedding)}"
                )


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Return a shared embedding service instance."""
    return EmbeddingService()