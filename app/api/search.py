from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.dependencies import get_search_service
from app.models import SearchRequest, SearchResponse
from app.services.embeddings import EmbeddingError
from app.services.search import SearchError, SearchService
from app.services.vector_store import VectorStoreError


router = APIRouter()


@router.post(
    "/search/",
    response_model=SearchResponse,
)
def search_documents(
    request: SearchRequest,
    search_service: Annotated[
        SearchService,
        Depends(get_search_service),
    ],
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
            status_code=500,
            content={"error": str(exc)},
        )

    except VectorStoreError:
        return JSONResponse(
            status_code=500,
            content={"error": "Search processing failed."},
        )