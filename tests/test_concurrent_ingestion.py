"""Integration tests for concurrent PDF uploads.

These tests expect the FastAPI application and Qdrant to already be running.

Example:
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up
    docker compose exec app pytest tests/test_concurrent_ingestion.py -v
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fitz

from app.dependencies import get_vector_store


BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
COLLECTION_NAME = "documents"
REQUEST_TIMEOUT_SECONDS = 60


def _make_pdf(text: str) -> bytes:
    """Create a small real PDF entirely in memory."""
    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), text)
        return document.tobytes()
    finally:
        document.close()


def _multipart_body(
    filename: str,
    content: bytes,
) -> tuple[bytes, str]:
    """Build a multipart/form-data request body."""
    boundary = "----pdf-semantic-search-test-boundary"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="input"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8")

    body += content
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")

    return body, f"multipart/form-data; boundary={boundary}"


def _post_upload(filename: str, content: bytes) -> dict:
    """Send one real HTTP upload request to the running API."""
    body, content_type = _multipart_body(filename, content)

    request = Request(
        f"{BASE_URL}/ingest/",
        data=body,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            payload = response.read().decode("utf-8")
            return {
                "status": response.status,
                "body": json.loads(payload),
            }

    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(
            f"Upload failed with HTTP {exc.code}: {error_body}"
        ) from exc

    except URLError as exc:
        raise AssertionError(
            f"Could not reach {BASE_URL}/ingest/. "
            "Make sure the Docker Compose stack is running."
        ) from exc


def _concurrent_uploads(
    documents: list[tuple[str, bytes]],
) -> list[dict]:
    """Start uploads together so the server receives overlapping requests."""
    barrier = Barrier(len(documents))

    def upload(document: tuple[str, bytes]) -> dict:
        filename, content = document

        barrier.wait(timeout=REQUEST_TIMEOUT_SECONDS)

        return _post_upload(filename, content)

    with ThreadPoolExecutor(max_workers=len(documents)) as executor:
        futures = [
            executor.submit(upload, document)
            for document in documents
        ]

        return [future.result() for future in futures]


def _point_count() -> int:
    """Read the current point count from the application's Qdrant collection."""
    vector_store = get_vector_store()

    return vector_store.client.count(
        collection_name=COLLECTION_NAME,
        exact=True,
    ).count


def _assert_success(
    response: dict,
    filename: str,
) -> None:
    """Validate the standard successful ingestion response."""
    assert response["status"] == 200
    assert response["body"]["files"] == [filename]
    assert "Successfully ingested" in response["body"]["message"]


def test_concurrent_uploads_of_different_pdfs_are_isolated() -> None:
    """Different documents can be ingested concurrently without interference."""
    documents = [
        (
            "concurrency-alpha.pdf",
            _make_pdf(
                "CONCURRENCY_UNIQUE_ALPHA: "
                "distributed systems and vector search."
            ),
        ),
        (
            "concurrency-beta.pdf",
            _make_pdf(
                "CONCURRENCY_UNIQUE_BETA: "
                "database indexing and semantic retrieval."
            ),
        ),
        (
            "concurrency-gamma.pdf",
            _make_pdf(
                "CONCURRENCY_UNIQUE_GAMMA: "
                "API request handling and embeddings."
            ),
        ),
        (
            "concurrency-delta.pdf",
            _make_pdf(
                "CONCURRENCY_UNIQUE_DELTA: "
                "container orchestration and service health."
            ),
        ),
    ]

    responses = _concurrent_uploads(documents)

    for (filename, _), response in zip(documents, responses):
        _assert_success(response, filename)


def test_same_pdf_uploaded_concurrently_is_idempotent() -> None:
    """Concurrent uploads of identical bytes should not create duplicate points."""
    filename = "concurrency-idempotent.pdf"

    content = _make_pdf(
        "CONCURRENCY_IDEMPOTENCY_MARKER: "
        "the exact same document uploaded concurrently."
    )

    # Establish the expected state for this exact document first.
    #
    # Because document identity is content-based and point IDs are deterministic,
    # later uploads of the same bytes should overwrite the same points rather than
    # create additional points.
    first_response = _post_upload(filename, content)

    _assert_success(first_response, filename)

    count_after_first_upload = _point_count()

    duplicate_documents = [
        (
            f"concurrency-idempotent-{index}.pdf",
            content,
        )
        for index in range(5)
    ]

    responses = _concurrent_uploads(duplicate_documents)

    for (duplicate_filename, _), response in zip(
        duplicate_documents,
        responses,
    ):
        _assert_success(response, duplicate_filename)

    count_after_concurrent_uploads = _point_count()

    assert (
        count_after_concurrent_uploads
        == count_after_first_upload
    )