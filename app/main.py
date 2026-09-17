from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.ingest import router as ingest_router
from app.api.search import router as search_router
from app.dependencies import get_vector_store


vector_store = get_vector_store()
qdrant_client = vector_store.client


def wait_for_qdrant(
    max_attempts: int = 30,
    delay_seconds: int = 1,
) -> None:
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

            # Startup-only blocking wait. Qdrant is expected to become
            # available quickly, so keeping this simple is preferable.
            import time

            time.sleep(delay_seconds)

    raise RuntimeError(
        "Qdrant did not become available in time."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle.

    Startup:
        - wait for Qdrant
        - ensure the collection exists

    Shutdown:
        - nothing currently requires explicit cleanup
    """
    wait_for_qdrant()
    vector_store.ensure_collection()

    yield


app = FastAPI(
    title="PDF Ingestor & Semantic Search API",
    version="1.0.0",
    description=(
        "A simple API that ingests PDF documents, generates embeddings, "
        "and enables semantic search over the ingested content."
    ),
    lifespan=lifespan,
)


app.include_router(ingest_router)
app.include_router(search_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Basic health check for the service."""
    try:
        qdrant_client.get_collections()
        return {
            "status": "ok",
            "qdrant": "connected",
        }
    except Exception:
        return {
            "status": "degraded",
            "qdrant": "unavailable",
        }