def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    source_filename: str | None = None,
    source_suffix: str | None = None,
) -> list[dict]:
    """Split text into overlapping character-based chunks."""
    if chunk_size <= 0:
        raise ValueError("chunk_size_must_be_positive")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap_must_be_non_negative")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap_must_be_smaller_than_chunk_size")

    normalized_text = text.strip()

    if not normalized_text:
        return []

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(normalized_text):
        end = min(start + chunk_size, len(normalized_text))
        chunk_content = normalized_text[start:end]

        chunks.append(
            {
                "chunk_id": f"{source_filename or 'document'}::chunk_{chunk_index}",
                "chunk_index": chunk_index,
                "source_filename": source_filename,
                "source_suffix": source_suffix,
                "start_char": start,
                "end_char": end,
                "char_count": len(chunk_content),
                "content": chunk_content,
            }
        )

        if end == len(normalized_text):
            break

        start = end - chunk_overlap
        chunk_index += 1

    return chunks