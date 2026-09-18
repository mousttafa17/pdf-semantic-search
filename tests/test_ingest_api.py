import io
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_ingestion_service
from app.main import app

from app.services.embeddings import EmbeddingError
from app.services.ingestion import IngestionError, IngestionResult
from app.services.vector_store import VectorStoreError


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


class RecordingIngestionService:
    """Fake service that records which files were ingested."""

    def __init__(self) -> None:
        self.ingested_files: list[str] = []

    def ingest(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> IngestionResult:
        self.ingested_files.append(filename)

        return IngestionResult(
            document_id=f"fake-{filename}",
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


def create_pdf_file(path: Path, text: str) -> None:
    path.write_bytes(create_pdf_bytes(text))


@pytest.fixture
def client():
    app.dependency_overrides[get_ingestion_service] = (
        lambda: FakeIngestionService()
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def recording_client():
    service = RecordingIngestionService()

    app.dependency_overrides[get_ingestion_service] = lambda: service

    with TestClient(app) as test_client:
        yield test_client, service

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


def test_ingest_multiple_pdfs(recording_client):
    client, service = recording_client

    pdf_one = create_pdf_bytes("First document.")
    pdf_two = create_pdf_bytes("Second document.")

    response = client.post(
        "/ingest/",
        files=[
            (
                "input",
                (
                    "first.pdf",
                    io.BytesIO(pdf_one),
                    "application/pdf",
                ),
            ),
            (
                "input",
                (
                    "second.pdf",
                    io.BytesIO(pdf_two),
                    "application/pdf",
                ),
            ),
        ],
    )

    assert response.status_code == 200

    body = response.json()

    assert body["message"] == (
        "Successfully ingested 2 PDF documents."
    )
    assert body["files"] == [
        "first.pdf",
        "second.pdf",
    ]
    assert service.ingested_files == [
        "first.pdf",
        "second.pdf",
    ]


def test_ingest_directory(recording_client, tmp_path):
    client, service = recording_client

    create_pdf_file(
        tmp_path / "document_a.pdf",
        "First directory document.",
    )
    create_pdf_file(
        tmp_path / "document_b.pdf",
        "Second directory document.",
    )

    response = client.post(
        "/ingest/",
        files={
            "input": (
                None,
                str(tmp_path),
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["message"] == (
        "Successfully ingested 2 PDF documents."
    )
    assert body["files"] == [
        "document_a.pdf",
        "document_b.pdf",
    ]
    assert service.ingested_files == [
        "document_a.pdf",
        "document_b.pdf",
    ]


def test_ingest_directory_ignores_non_pdf_files(
    recording_client,
    tmp_path,
):
    client, service = recording_client

    create_pdf_file(
        tmp_path / "document.pdf",
        "PDF document.",
    )

    (tmp_path / "notes.txt").write_text(
        "This file should not be ingested."
    )

    (tmp_path / "image.png").write_bytes(
        b"not actually an image"
    )

    response = client.post(
        "/ingest/",
        files={
            "input": (
                None,
                str(tmp_path),
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["message"] == (
        "Successfully ingested 1 PDF documents."
    )
    assert body["files"] == ["document.pdf"]
    assert service.ingested_files == ["document.pdf"]


def test_ingest_rejects_missing_directory(
    recording_client,
    tmp_path,
):
    client, service = recording_client

    missing_directory = tmp_path / "does-not-exist"

    response = client.post(
        "/ingest/",
        files={
            "input": (
                None,
                str(missing_directory),
            )
        },
    )

    assert response.status_code == 400

    assert response.json() == {
        "error": "Directory does not exist."
    }

    assert service.ingested_files == []


def test_ingest_rejects_mixed_files_and_directory(
    recording_client,
    tmp_path,
):
    client, service = recording_client

    pdf_bytes = create_pdf_bytes("Uploaded document.")

    create_pdf_file(
        tmp_path / "directory.pdf",
        "Directory document.",
    )

    response = client.post(
        "/ingest/",
        files=[
            (
                "input",
                (
                    "uploaded.pdf",
                    io.BytesIO(pdf_bytes),
                    "application/pdf",
                ),
            ),
            (
                "input",
                (
                    None,
                    str(tmp_path),
                ),
            ),
        ],
    )

    assert response.status_code == 400

    assert response.json() == {
        "error": (
            "Input must be either PDF files or a directory path."
        )
    }

    assert service.ingested_files == []


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


class EmbeddingFailureIngestionService:
    def ingest(self, file_bytes: bytes, filename: str):
        raise EmbeddingError("Test embedding failure.")


class VectorStoreFailureIngestionService:
    def ingest(self, file_bytes: bytes, filename: str):
        raise VectorStoreError("Test vector store failure.")


class UnexpectedFailureIngestionService:
    def ingest(self, file_bytes: bytes, filename: str):
        raise RuntimeError("Test unexpected failure.")


def test_ingest_endpoint_returns_500_on_embedding_failure(client):
    app.dependency_overrides[get_ingestion_service] = (
        lambda: EmbeddingFailureIngestionService()
    )

    response = client.post(
        "/ingest/",
        files={
            "input": (
                "sample.pdf",
                b"%PDF-test-content%",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": "Internal server error."
    }


def test_ingest_endpoint_returns_500_on_vector_store_failure(client):
    app.dependency_overrides[get_ingestion_service] = (
        lambda: VectorStoreFailureIngestionService()
    )

    response = client.post(
        "/ingest/",
        files={
            "input": (
                "sample.pdf",
                b"%PDF-test-content%",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": "Internal server error."
    }


def test_ingest_endpoint_returns_500_on_unexpected_error(client):
    app.dependency_overrides[get_ingestion_service] = (
        lambda: UnexpectedFailureIngestionService()
    )

    response = client.post(
        "/ingest/",
        files={
            "input": (
                "sample.pdf",
                b"%PDF-test-content%",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": "Internal server error."
    }

def test_ingest_rejects_missing_input(client):
    response = client.post(
        "/ingest/",
        files={},
    )

    assert response.status_code == 400
    assert "error" in response.json()

def test_ingest_rejects_empty_directory(
    recording_client,
    tmp_path,
):
    client, service = recording_client

    response = client.post(
        "/ingest/",
        files={
            "input": (
                None,
                str(tmp_path),
            )
        },
    )

    assert response.status_code == 400
    assert "error" in response.json()
    assert service.ingested_files == []

def test_ingest_rejects_directory_path_pointing_to_file(
    recording_client,
    tmp_path,
):
    client, service = recording_client

    file_path = tmp_path / "not-a-directory.pdf"
    create_pdf_file(
        file_path,
        "This is actually a file.",
    )

    response = client.post(
        "/ingest/",
        files={
            "input": (
                None,
                str(file_path),
            )
        },
    )

    assert response.status_code == 400
    assert "error" in response.json()
    assert service.ingested_files == []

def test_ingest_accepts_unicode_filename(
    recording_client,
):
    client, service = recording_client

    pdf_bytes = create_pdf_bytes(
        "Unicode filename test."
    )

    filename = "مستند-اختبار.pdf"

    response = client.post(
        "/ingest/",
        files={
            "input": (
                filename,
                io.BytesIO(pdf_bytes),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    assert response.json()["files"] == [filename]
    assert service.ingested_files == [filename]
