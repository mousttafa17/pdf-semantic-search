import pytest

from app.services.chunking import ChunkingError, chunk_text


def test_short_text_returns_single_chunk():
    text = "Artificial intelligence enables systems to learn from data."

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 1
    assert chunks[0].content == text
    assert chunks[0].chunk_index == 0


def test_long_text_is_split_into_multiple_chunks():
    text = "A" * 250

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 3
    assert all(len(chunk.content) <= 100 for chunk in chunks)


def test_chunks_have_sequential_indexes():
    text = "A" * 250

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]


def test_chunks_overlap():
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    chunks = chunk_text(
        text,
        chunk_size=10,
        chunk_overlap=3,
    )

    assert chunks[0].content == "ABCDEFGHIJ"
    assert chunks[1].content.startswith("HIJ")


def test_whitespace_is_removed():
    text = "   First sentence.\n\nSecond sentence.   "

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert chunks[0].content == "First sentence.\n\nSecond sentence."


def test_empty_text_is_rejected():
    with pytest.raises(ChunkingError, match="empty"):
        chunk_text("")


def test_whitespace_only_text_is_rejected():
    with pytest.raises(ChunkingError, match="empty"):
        chunk_text("   \n\t  ")


def test_invalid_chunk_size_is_rejected():
    with pytest.raises(ChunkingError, match="chunk_size"):
        chunk_text("some text", chunk_size=0)


def test_negative_overlap_is_rejected():
    with pytest.raises(ChunkingError, match="negative"):
        chunk_text(
            "some text",
            chunk_size=100,
            chunk_overlap=-1,
        )


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ChunkingError, match="smaller"):
        chunk_text(
            "some text",
            chunk_size=100,
            chunk_overlap=100,
        )