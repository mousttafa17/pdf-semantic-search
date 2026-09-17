import fitz
import pytest
import uuid
import logging

from app.services.ingestion import IngestionService, IngestionError
from app.services.vector_store import VectorStore
from app.services.pdf import PDFProcessingError


class FakeEmbeddingService:
    """Deterministic embedding service for integration tests."""

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [
            [0.1] * 384
            for _ in texts
        ]


def create_pdf_bytes(*page_texts: str) -> bytes:
    """Create an in-memory PDF."""
    document = fitz.open()

    for page_text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), page_text)

    pdf_bytes = document.tobytes()
    document.close()

    return pdf_bytes


@pytest.fixture
def vector_store() -> VectorStore:
    collection_name = f"test-documents-{uuid.uuid4().hex}"

    store = VectorStore(
        collection_name=collection_name,
    )

    store.ensure_collection()

    yield store

    if store.collection_exists():
        store.client.delete_collection(
            store.collection_name
        )


def test_ingest_pdf_end_to_end(vector_store: VectorStore):
    embedding_service = FakeEmbeddingService()

    ingestion_service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    pdf_bytes = create_pdf_bytes(
        "Artificial intelligence enables systems to learn from data."
    )

    result = ingestion_service.ingest(
        file_bytes=pdf_bytes,
        filename="sample.pdf",
    )

    assert result.filename == "sample.pdf"
    assert result.chunk_count == 1
    assert len(result.document_id) == 64

    points = vector_store.client.scroll(
        collection_name=vector_store.collection_name,
        limit=10,
        with_payload=True,
        with_vectors=True,
    )[0]

    assert len(points) == 1

    point = points[0]

    assert point.payload["document_id"] == result.document_id
    assert point.payload["document"] == "sample.pdf"
    assert point.payload["chunk_index"] == 0
    assert "Artificial intelligence" in point.payload["content"]
    assert len(point.vector) == 384


def test_same_document_gets_same_document_id(
    vector_store: VectorStore,
):
    embedding_service = FakeEmbeddingService()

    ingestion_service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    pdf_bytes = create_pdf_bytes(
        "The same document should produce the same ID."
    )

    first_result = ingestion_service.ingest(
        file_bytes=pdf_bytes,
        filename="first-name.pdf",
    )

    second_result = ingestion_service.ingest(
        file_bytes=pdf_bytes,
        filename="second-name.pdf",
    )

    assert first_result.document_id == second_result.document_id


def test_different_documents_get_different_ids(
    vector_store: VectorStore,
):
    embedding_service = FakeEmbeddingService()

    ingestion_service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    first_pdf = create_pdf_bytes("First document.")
    second_pdf = create_pdf_bytes("Second document.")

    first_result = ingestion_service.ingest(
        file_bytes=first_pdf,
        filename="first.pdf",
    )

    second_result = ingestion_service.ingest(
        file_bytes=second_pdf,
        filename="second.pdf",
    )

    assert first_result.document_id != second_result.document_id


def test_invalid_pdf_raises_pdf_processing_error(
    vector_store: VectorStore,
):
    embedding_service = FakeEmbeddingService()

    ingestion_service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    with pytest.raises(
        PDFProcessingError,
        match="The uploaded file is not a valid PDF.",
    ):  
        ingestion_service.ingest(
            file_bytes=b"\x00\x01\x02\xff\xfe\x00\xab\xcd",
            filename="bad.pdf",
        )

def test_ingest_assessment_text_fixture(
    vector_store: VectorStore,
):
    embedding_service = FakeEmbeddingService()

    ingestion_service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    result = ingestion_service.ingest(
        file_bytes=(
            b"Artificial intelligence enables systems "
            b"to learn from data."
        ),
        filename="sample.pdf",
    )

    assert result.filename == "sample.pdf"
    assert result.chunk_count == 1
    assert len(result.document_id) == 64

class UnexpectedEmbeddingService:
    def embed_documents(self, texts):
        raise RuntimeError("Unexpected embedding failure.")

def test_unexpected_ingestion_error_is_wrapped(
    vector_store: VectorStore,
):
    ingestion_service = IngestionService(
        embedding_service=UnexpectedEmbeddingService(),
        vector_store=vector_store,
    )

    pdf_bytes = create_pdf_bytes(
        "Artificial intelligence enables systems to learn from data."
    )

    with pytest.raises(
        IngestionError,
        match="Failed to ingest document",
    ):
        ingestion_service.ingest(
            file_bytes=pdf_bytes,
            filename="sample.pdf",
        )

def test_ingestion_logs_metadata_without_document_content(
    vector_store: VectorStore,
    caplog,
):
    embedding_service = FakeEmbeddingService()

    ingestion_service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    document_text = (
        "Artificial intelligence enables systems to learn from data."
    )

    caplog.set_level(logging.INFO, logger="app.services.ingestion")

    pdf_bytes = create_pdf_bytes(document_text)

    ingestion_service.ingest(
        file_bytes=pdf_bytes,
        filename="sample.pdf",
    )

    assert "Ingestion started" in caplog.text
    assert "Ingestion completed" in caplog.text
    assert "filename=sample.pdf" in caplog.text
    assert "chunks=1" in caplog.text
    assert document_text not in caplog.text