import fitz
import pytest

from app.services.pdf import PDFProcessingError, extract_text_from_pdf


def create_pdf_bytes(*page_texts: str) -> bytes:
    """Create a small in-memory PDF for testing."""
    document = fitz.open()

    for page_text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), page_text)

    pdf_bytes = document.tobytes()
    document.close()

    return pdf_bytes


def test_extract_text_from_single_page_pdf():
    pdf_bytes = create_pdf_bytes(
        "Artificial intelligence enables systems to learn from data."
    )

    result = extract_text_from_pdf(pdf_bytes, "sample.pdf")

    assert result.filename == "sample.pdf"
    assert "Artificial intelligence" in result.text
    assert "learn from data" in result.text


def test_extract_text_from_multiple_pages():
    pdf_bytes = create_pdf_bytes(
        "First page contains information about embeddings.",
        "Second page contains information about semantic search.",
    )

    result = extract_text_from_pdf(pdf_bytes, "sample.pdf")

    assert "embeddings" in result.text
    assert "semantic search" in result.text


def test_rejects_invalid_pdf():
    # Binary/corrupted content should still be rejected.
    invalid_bytes = b"\x00\x01\x02\xff\xfe\x00\xab\xcd"

    with pytest.raises(PDFProcessingError, match="valid PDF"):
        extract_text_from_pdf(invalid_bytes, "sample.pdf")


def test_rejects_empty_file():
    with pytest.raises(PDFProcessingError, match="empty"):
        extract_text_from_pdf(b"", "sample.pdf")


def test_rejects_textless_pdf():
    document = fitz.open()
    document.new_page()
    pdf_bytes = document.tobytes()
    document.close()

    with pytest.raises(
        PDFProcessingError,
        match="no extractable text",
    ):
        extract_text_from_pdf(pdf_bytes, "empty.pdf")

def test_accepts_assessment_text_fixture():
    file_bytes = (
        b"Artificial intelligence enables systems to learn from data."
    )

    result = extract_text_from_pdf(
        file_bytes,
        "sample.pdf",
    )

    assert result.filename == "sample.pdf"
    assert result.text == (
        "Artificial intelligence enables systems to learn from data."
    )

def test_extract_text_preserves_unicode_text():
    pdf_bytes = create_pdf_bytes(
        "Café résumé naïve"
    )

    result = extract_text_from_pdf(
        pdf_bytes,
        "unicode.pdf",
    )

    assert "Café résumé naïve" in result.text