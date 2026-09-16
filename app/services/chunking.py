from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """A chunk of document text."""

    content: str
    chunk_index: int


class ChunkingError(Exception):
    """Raised when text cannot be chunked."""


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[TextChunk]:
    """
    Split text into overlapping chunks.

    Args:
        text: Input document text.
        chunk_size: Maximum number of characters in each chunk.
        chunk_overlap: Number of characters shared between adjacent chunks.

    Returns:
        A list of TextChunk objects.

    Raises:
        ChunkingError: If the configuration is invalid or the text is empty.
    """
    if not text or not text.strip():
        raise ChunkingError("Cannot chunk empty text.")

    if chunk_size <= 0:
        raise ChunkingError("chunk_size must be greater than zero.")

    if chunk_overlap < 0:
        raise ChunkingError("chunk_overlap cannot be negative.")

    if chunk_overlap >= chunk_size:
        raise ChunkingError(
            "chunk_overlap must be smaller than chunk_size."
        )

    cleaned_text = text.strip()

    chunks: list[TextChunk] = []

    start = 0
    chunk_index = 0
    text_length = len(cleaned_text)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        chunk_content = cleaned_text[start:end].strip()

        if chunk_content:
            chunks.append(
                TextChunk(
                    content=chunk_content,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

        if end == text_length:
            break

        start = end - chunk_overlap

    return chunks