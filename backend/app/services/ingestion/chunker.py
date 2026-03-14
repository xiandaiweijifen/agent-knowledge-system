import re


def build_chunk_record(
    *,
    chunk_index: int,
    source_filename: str | None,
    source_suffix: str | None,
    start_char: int,
    end_char: int,
    content: str,
) -> dict:
    """Build a normalized chunk payload."""
    return {
        "chunk_id": f"{source_filename or 'document'}::chunk_{chunk_index}",
        "chunk_index": chunk_index,
        "source_filename": source_filename,
        "source_suffix": source_suffix,
        "start_char": start_char,
        "end_char": end_char,
        "char_count": len(content),
        "content": content,
    }


def validate_chunk_config(chunk_size: int, chunk_overlap: int) -> None:
    """Validate chunk sizing parameters."""
    if chunk_size <= 0:
        raise ValueError("chunk_size_must_be_positive")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap_must_be_non_negative")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap_must_be_smaller_than_chunk_size")


def chunk_text_by_character(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    source_filename: str | None,
    source_suffix: str | None,
) -> list[dict]:
    """Split text into overlapping character-based chunks."""
    min_chunk_size = max(1, chunk_size // 5)
    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Merge tiny tail fragments into the previous chunk to reduce noise.
        if len(text) - end < min_chunk_size:
            end = len(text)

        chunk_content = text[start:end]

        chunks.append(
            build_chunk_record(
                chunk_index=chunk_index,
                source_filename=source_filename,
                source_suffix=source_suffix,
                start_char=start,
                end_char=end,
                content=chunk_content,
            )
        )

        if end == len(text):
            break

        start = end - chunk_overlap
        chunk_index += 1

    return chunks


def chunk_text_by_paragraph(
    text: str,
    chunk_size: int,
    source_filename: str | None,
    source_suffix: str | None,
) -> list[dict]:
    """Split text with paragraph-aware packing up to the target chunk size."""
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    if not paragraphs:
        return []

    chunks = []
    chunk_index = 0
    search_start = 0
    current_content = ""
    current_start = 0

    for paragraph in paragraphs:
        paragraph_start = text.find(paragraph, search_start)

        if paragraph_start == -1:
            paragraph_start = search_start

        paragraph_end = paragraph_start + len(paragraph)

        if not current_content:
            current_content = paragraph
            current_start = paragraph_start
            search_start = paragraph_end
            continue

        candidate_content = f"{current_content}\n\n{paragraph}"

        if len(candidate_content) <= chunk_size:
            current_content = candidate_content
            search_start = paragraph_end
            continue

        chunks.append(
            build_chunk_record(
                chunk_index=chunk_index,
                source_filename=source_filename,
                source_suffix=source_suffix,
                start_char=current_start,
                end_char=current_start + len(current_content),
                content=current_content,
            )
        )
        chunk_index += 1

        if len(paragraph) <= chunk_size:
            current_content = paragraph
            current_start = paragraph_start
        else:
            paragraph_chunks = chunk_text_by_character(
                text=paragraph,
                chunk_size=chunk_size,
                chunk_overlap=0,
                source_filename=source_filename,
                source_suffix=source_suffix,
            )

            for paragraph_chunk in paragraph_chunks:
                chunk_content = paragraph_chunk["content"]
                chunk_length = paragraph_chunk["char_count"]
                relative_start = paragraph_chunk["start_char"]

                chunks.append(
                    build_chunk_record(
                        chunk_index=chunk_index,
                        source_filename=source_filename,
                        source_suffix=source_suffix,
                        start_char=paragraph_start + relative_start,
                        end_char=paragraph_start + relative_start + chunk_length,
                        content=chunk_content,
                    )
                )
                chunk_index += 1

            current_content = ""
            current_start = paragraph_end

        search_start = paragraph_end

    if current_content:
        chunks.append(
            build_chunk_record(
                chunk_index=chunk_index,
                source_filename=source_filename,
                source_suffix=source_suffix,
                start_char=current_start,
                end_char=current_start + len(current_content),
                content=current_content,
            )
        )

    return chunks


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    chunk_strategy: str = "character",
    source_filename: str | None = None,
    source_suffix: str | None = None,
) -> list[dict]:
    """Split text into retrievable chunks with a configurable strategy."""
    validate_chunk_config(chunk_size, chunk_overlap)

    normalized_text = text.strip()

    if not normalized_text:
        return []

    normalized_strategy = chunk_strategy.strip().lower()

    if normalized_strategy == "character":
        return chunk_text_by_character(
            text=normalized_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            source_filename=source_filename,
            source_suffix=source_suffix,
        )

    if normalized_strategy == "paragraph":
        return chunk_text_by_paragraph(
            text=normalized_text,
            chunk_size=chunk_size,
            source_filename=source_filename,
            source_suffix=source_suffix,
        )

    raise ValueError("unsupported_chunk_strategy")
