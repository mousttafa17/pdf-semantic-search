import hashlib
import uuid
from collections.abc import Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

from app.config import EMBEDDING_DIMENSION, QDRANT_URL


COLLECTION_NAME = "documents"


class VectorStoreError(Exception):
    """Raised when a vector-store operation fails."""


class VectorStore:
    """Handles persistence and retrieval of document embeddings in Qdrant."""

    def __init__(
        self,
        url: str = QDRANT_URL,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self.client = QdrantClient(url=url)
        self.collection_name = collection_name

    def collection_exists(self) -> bool:
        """Return whether the configured collection exists."""
        try:
            collections = self.client.get_collections().collections
        except Exception as exc:
            raise VectorStoreError(
                "Failed to check Qdrant collections."
            ) from exc

        return any(
            collection.name == self.collection_name
            for collection in collections
        )

    def create_collection(self) -> None:
        """Create the vector collection if it does not already exist."""
        if self.collection_exists():
            return

        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
        except Exception as exc:
            raise VectorStoreError(
                "Failed to create Qdrant collection."
            ) from exc

        print(
            f"Created Qdrant collection: {self.collection_name}"
        )

    def ensure_collection(self) -> None:
        """Ensure the required collection exists."""
        self.create_collection()

    def upsert_chunks(
        self,
        document_id: str,
        document_name: str,
        chunks: Sequence[str],
        embeddings: Sequence[Sequence[float]],
    ) -> int:
        """
        Store document chunks and their embeddings in Qdrant.

        Each chunk gets a deterministic UUID derived from the document ID
        and chunk index. Re-ingesting the same document therefore updates
        the same points instead of creating duplicate points.
        """
        if len(chunks) != len(embeddings):
            raise VectorStoreError(
                "Number of chunks must match number of embeddings."
            )

        if not chunks:
            return 0

        self.ensure_collection()

        points: list[PointStruct] = []

        for chunk_index, (chunk, embedding) in enumerate(
            zip(chunks, embeddings)
        ):
            self._validate_embedding(embedding)

            point_id = self._generate_point_id(
                document_id=document_id,
                chunk_index=chunk_index,
            )

            points.append(
                PointStruct(
                    id=point_id,
                    vector=list(embedding),
                    payload={
                        "document_id": document_id,
                        "document": document_name,
                        "chunk_index": chunk_index,
                        "content": chunk,
                    },
                )
            )

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreError(
                "Failed to store document chunks in Qdrant."
            ) from exc

        return len(points)

    def get_points(
        self,
        point_ids: Sequence[str],
    ) -> list:
        """Retrieve points by their IDs. Primarily useful for testing/debugging."""
        if not point_ids:
            return []

        try:
            return self.client.retrieve(
                collection_name=self.collection_name,
                ids=list(point_ids),
            )
        except Exception as exc:
            raise VectorStoreError(
                "Failed to retrieve points from Qdrant."
            ) from exc

    @staticmethod
    def _generate_point_id(
        document_id: str,
        chunk_index: int,
    ) -> str:
        """
        Generate a deterministic UUID for a document chunk.

        UUID5 is deterministic for a given namespace/name pair, making
        repeated ingestion of the same document chunk idempotent.
        """
        namespace = uuid.UUID("8e4d5f1e-d0b4-4e47-a5f8-c0f3f4e7e4e0")

        return str(
            uuid.uuid5(
                namespace,
                f"{document_id}:{chunk_index}",
            )
        )

    @staticmethod
    def _validate_embedding(
        embedding: Sequence[float],
    ) -> None:
        if len(embedding) != EMBEDDING_DIMENSION:
            raise VectorStoreError(
                "Embedding dimension mismatch: "
                f"expected {EMBEDDING_DIMENSION}, "
                f"got {len(embedding)}"
            )

    def search(
        self,
        query_embedding: Sequence[float],
        limit: int = 5,
    ) -> list:
        """
        Search for points most similar to a query embedding.

        Returns Qdrant scored points ordered by decreasing similarity.
        """
        if not query_embedding:
            raise VectorStoreError(
                "Query embedding cannot be empty."
            )

        if limit <= 0:
            raise VectorStoreError(
                "Search limit must be greater than zero."
            )

        self._validate_embedding(query_embedding)

        if not self.collection_exists():
            return []

        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=list(query_embedding),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            ).points
        except Exception as exc:
            raise VectorStoreError(
                "Failed to search Qdrant."
            ) from exc

        return results