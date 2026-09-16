from dataclasses import dataclass
from io import BytesIO

import fitz


class PDFProcessingError(Exception):
    """Raised when a PDF cannot be processed successfully."""


@dataclass(frozen=True)
class ExtractedDocument:
    """Text extracted from a single PDF document."""

    filename: str
    text: str


def extract_text_from_pdf(
    file_bytes: bytes,
    filename: str,
) -> ExtractedDocument:
    """
    Extract text from a PDF represented by raw bytes.

    Raises:
        PDFProcessingError: If the file is not a valid/readable PDF or
        contains no extractable text.
    """
    if not file_bytes:
        raise PDFProcessingError("The uploaded file is empty.")

    try:
        document = fitz.open(stream=BytesIO(file_bytes), filetype="pdf")
    except Exception as exc:
        raise PDFProcessingError("The uploaded file is not a valid PDF.") from exc

    try:
        pages = []

        for page in document:
            text = page.get_text("text")

            if text:
                pages.append(text)

        extracted_text = "\n".join(pages)
    except Exception as exc:
        raise PDFProcessingError("Failed to extract text from PDF.") from exc
    finally:
        document.close()

    cleaned_text = normalize_text(extracted_text)

    if not cleaned_text:
        raise PDFProcessingError(
            "The PDF contains no extractable text."
        )

    return ExtractedDocument(
        filename=filename,
        text=cleaned_text,
    )


def normalize_text(text: str) -> str:
    """
    Normalize whitespace while preserving paragraph boundaries.

    This intentionally keeps the cleaning step conservative so that
    document structure is not unnecessarily destroyed before chunking.
    """
    lines = []

    for line in text.splitlines():
        cleaned_line = " ".join(line.split())

        if cleaned_line:
            lines.append(cleaned_line)

    return "\n".join(lines)