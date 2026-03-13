from pathlib import Path


TEXT_FILE_SUFFIXES = {".txt", ".md"}


def extract_text_from_file(file_path: Path) -> str:
    """Extract plain text content from a supported local document."""
    if file_path.suffix.lower() not in TEXT_FILE_SUFFIXES:
        raise ValueError("unsupported_file_type")

    try:
        # Keep UTF-8 as the baseline contract for the initial ingestion pipeline.
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("text_decode_error") from exc
