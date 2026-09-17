from pydantic import BaseModel


class SearchRequest(BaseModel):
    """Search request body."""

    query: str


class SearchResultResponse(BaseModel):
    """Single search result returned by the API."""

    document: str
    score: float
    content: str


class SearchResponse(BaseModel):
    """Semantic search response."""

    results: list[SearchResultResponse]