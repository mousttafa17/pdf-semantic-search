import hashlib
from dataclasses import dataclass

from app.services.chunking import TextChunk, chunk_text, ChunkingError
from app.services.embeddings import EmbeddingService, EmbeddingError
from app.services.pdf import extract_text_from_pdf, PDFProcessingError
from app.services.vector_store import VectorStore, VectorStoreError


class IngestionError(Exception):
    """Raised when document ingestion fails."""


@dataclass(frozen=True)
class IngestionResult:
    """Summary of a successfully ingested document."""

    document_id: str
    filename: str
    chunk_count: int


class IngestionService:
    """
    Orchestrates the complete document ingestion pipeline.

    PDF bytes
        -> text extraction
        -> chunking
        -> embedding generation
        -> Qdrant storage
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def ingest(self, file_bytes: bytes, filename: str) -> IngestionResult:
        document_id = self._generate_document_id(file_bytes)
    
        try:
            extracted_document = extract_text_from_pdf(
                file_bytes=file_bytes,
                filename=filename,
            )
    
            chunks = chunk_text(extracted_document.text)
    
            embeddings = self.embedding_service.embed_documents(
                [chunk.content for chunk in chunks]
            )
    
            self.vector_store.upsert_chunks(
                document_id=document_id,
                document_name=filename,
                chunks=chunks,
                embeddings=embeddings,
            )
    
            return IngestionResult(
                document_id=document_id,
                filename=filename,
                chunk_count=len(chunks),
            )
    
        except (PDFProcessingError, ChunkingError, EmbeddingError, VectorStoreError):
            raise
        
        except Exception as exc:
            raise IngestionError("Failed to ingest document.") from exc

    @staticmethod
    def _generate_document_id(file_bytes: bytes) -> str:
        """Generate a deterministic ID from the document contents."""
        return hashlib.sha256(file_bytes).hexdigest()