from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models import SearchRequest, SearchResponse
from app.services.embeddings import EmbeddingService, EmbeddingError
from app.services.search import SearchService, SearchError
from app.services.vector_store import VectorStore, VectorStoreError


router = APIRouter()


search_service = SearchService(
    embedding_service=EmbeddingService(),
    vector_store=VectorStore(),
)


@router.post(
    "/search/",
    response_model=SearchResponse,
)
def search_documents(
    request: SearchRequest,
) -> SearchResponse | JSONResponse:
    """Perform semantic search over ingested document chunks."""
    try:
        results = search_service.search(request.query)

        return SearchResponse(
            results=[
                {
                    "document": result.document,
                    "score": result.score,
                    "content": result.content,
                }
                for result in results
            ]
        )

    except SearchError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )

    except EmbeddingError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )

    except VectorStoreError:
        return JSONResponse(
            status_code=500,
            content={"error": "Search processing failed."},
        )