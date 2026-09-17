import io

import fitz
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_ingestion_service
from app.main import app
from app.services.ingestion import IngestionResult


class FakeIngestionService:
    def ingest(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> IngestionResult:
        return IngestionResult(
            document_id="fake-document-id",
            filename=filename,
            chunk_count=1,
        )


def create_pdf_bytes(text: str) -> bytes:
    document = fitz.open()

    page = document.new_page()
    page.insert_text((72, 72), text)

    pdf_bytes = document.tobytes()
    document.close()

    return pdf_bytes


@pytest.fixture
def client():
    app.dependency_overrides[get_ingestion_service] = (
        lambda: FakeIngestionService()
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_ingest_single_pdf(client):
    pdf_bytes = create_pdf_bytes(
        "Artificial intelligence enables systems to learn from data."
    )

    response = client.post(
        "/ingest/",
        files={
            "input": (
                "sample.pdf",
                io.BytesIO(pdf_bytes),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["message"] == (
        "Successfully ingested 1 PDF documents."
    )
    assert body["files"] == ["sample.pdf"]


def test_ingest_rejects_non_pdf(client):
    response = client.post(
        "/ingest/",
        files={
            "input": (
                "sample.txt",
                io.BytesIO(b"not a pdf"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 400

    assert response.json() == {
        "error": "Only PDF files are accepted."
    }


def test_ingest_rejects_empty_file(client):
    response = client.post(
        "/ingest/",
        files={
            "input": (
                "empty.pdf",
                io.BytesIO(b""),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400

    assert response.json() == {
        "error": "Uploaded file 'empty.pdf' is empty."
    }