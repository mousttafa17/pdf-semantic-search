import hashlib
import logging

from time import perf_counter
from dataclasses import dataclass

from app.services.chunking import TextChunk, chunk_text, ChunkingError
from app.services.embeddings import EmbeddingService, EmbeddingError
from app.services.pdf import extract_text_from_pdf, PDFProcessingError
from app.services.vector_store import VectorStore, VectorStoreError


logger = logging.getLogger(__name__)


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
        start_time = perf_counter()
    
        logger.info(
            "Ingestion started filename=%s document_id=%s",
            filename,
            document_id,
        )
    
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
    
            duration_ms = (perf_counter() - start_time) * 1000
    
            logger.info(
                "Ingestion completed filename=%s document_id=%s "
                "chunks=%d duration_ms=%.2f",
                filename,
                document_id,
                len(chunks),
                duration_ms,
            )
    
            return IngestionResult(
                document_id=document_id,
                filename=filename,
                chunk_count=len(chunks),
            )
    
        except (PDFProcessingError, ChunkingError) as exc:
            logger.warning(
                "Ingestion rejected filename=%s reason=%s",
                filename,
                str(exc),
            )
            raise
        
        except (EmbeddingError, VectorStoreError):
            logger.exception(
                "Ingestion infrastructure failure "
                "filename=%s document_id=%s",
                filename,
                document_id,
            )
            raise
        
        except Exception:
            logger.exception(
                "Unexpected ingestion failure "
                "filename=%s document_id=%s",
                filename,
                document_id,
            )
            raise IngestionError("Failed to ingest document.") from None

    @staticmethod
    def _generate_document_id(file_bytes: bytes) -> str:
        """Generate a deterministic ID from the document contents."""
        return hashlib.sha256(file_bytes).hexdigest()