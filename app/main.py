import time

from fastapi import FastAPI
from qdrant_client import QdrantClient

from app.config import QDRANT_URL
from app.services.vector_store import VectorStore


app = FastAPI(
    title="PDF Ingestor & Semantic Search API",
    version="1.0.0",
    description=(
        "A simple API that ingests PDF documents, generates embeddings, "
        "and enables semantic search over the ingested content."
    ),
)


qdrant_client = QdrantClient(url=QDRANT_URL)
vector_store = VectorStore()


def wait_for_qdrant(max_attempts: int = 30, delay_seconds: int = 1) -> None:
    """Wait until Qdrant is reachable."""
    for attempt in range(1, max_attempts + 1):
        try:
            qdrant_client.get_collections()
            print("Qdrant is ready.")
            return
        except Exception as exc:
            print(
                f"Waiting for Qdrant "
                f"(attempt {attempt}/{max_attempts}): {exc}"
            )
            time.sleep(delay_seconds)

    raise RuntimeError("Qdrant did not become available in time.")


@app.on_event("startup")
def startup_event() -> None:
    """Initialize external dependencies before accepting requests."""
    wait_for_qdrant()
    vector_store.ensure_collection()


@app.get("/health")
def health_check() -> dict[str, str]:
    """Basic health check for the service."""
    try:
        qdrant_client.get_collections()
        return {"status": "ok", "qdrant": "connected"}
    except Exception:
        return {"status": "degraded", "qdrant": "unavailable"}