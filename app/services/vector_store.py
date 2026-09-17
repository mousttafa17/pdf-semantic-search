from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import EMBEDDING_DIMENSION, QDRANT_URL


COLLECTION_NAME = "documents"


class VectorStore:
    """Handles all interactions with Qdrant."""

    def __init__(
        self,
        url: str = QDRANT_URL,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self.client = QdrantClient(url=url)
        self.collection_name = collection_name

    def collection_exists(self) -> bool:
        """Check whether the vector collection exists."""
        collections = self.client.get_collections().collections

        return any(
            collection.name == self.collection_name
            for collection in collections
        )

    def create_collection(self) -> None:
        """Create the vector collection if it does not already exist."""
        if self.collection_exists():
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )

        print(
            f"Created Qdrant collection: {self.collection_name}"
        )

    def ensure_collection(self) -> None:
        """Ensure the required Qdrant collection exists."""
        self.create_collection()