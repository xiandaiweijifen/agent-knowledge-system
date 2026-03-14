from app.services.ingestion.chunker import chunk_text


def test_chunk_text_supports_paragraph_strategy():
    text = (
        "Paragraph one explains what RAG means.\n\n"
        "Paragraph two explains why chunking matters.\n\n"
        "Paragraph three explains retrieval diagnostics."
    )

    chunks = chunk_text(
        text=text,
        chunk_size=60,
        chunk_overlap=10,
        chunk_strategy="paragraph",
        source_filename="sample.md",
        source_suffix=".md",
    )

    assert len(chunks) == 3
    assert chunks[0]["content"] == "Paragraph one explains what RAG means."
    assert chunks[1]["content"] == "Paragraph two explains why chunking matters."
    assert chunks[2]["content"] == "Paragraph three explains retrieval diagnostics."


def test_chunk_text_rejects_unsupported_strategy():
    try:
        chunk_text(
            text="example text",
            chunk_strategy="sentence",
        )
    except ValueError as exc:
        assert str(exc) == "unsupported_chunk_strategy"
    else:
        raise AssertionError("Expected unsupported_chunk_strategy")


def test_character_chunking_merges_tiny_tail_fragment():
    text = "a" * 62

    chunks = chunk_text(
        text=text,
        chunk_size=60,
        chunk_overlap=0,
        chunk_strategy="character",
        source_filename="sample.txt",
        source_suffix=".txt",
    )

    assert len(chunks) == 1
    assert chunks[0]["char_count"] == 62
