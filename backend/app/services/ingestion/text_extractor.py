from pathlib import Path


TEXT_FILE_SUFFIXES = {".txt", ".md"}


def extract_text_from_file(file_path: Path) -> str:
    """Extract plain text content from a supported local document."""
    if file_path.suffix not in TEXT_FILE_SUFFIXES:
        raise ValueError("unsupported_file_type")

    # Read text-based files with UTF-8 encoding for the initial MVP.
    return file_path.read_text(encoding="utf-8")