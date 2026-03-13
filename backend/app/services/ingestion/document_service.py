from pathlib import Path
import re


RAW_DATA_DIR = Path("../data/raw")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

TEXT_FILE_SUFFIXES = {".txt", ".md"}


def list_documents() -> list[dict]:
    """Return basic metadata for all uploaded documents."""
    documents = []

    for file_path in RAW_DATA_DIR.iterdir():
        if file_path.is_file():
            documents.append(
                {
                    "filename": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                    "suffix": file_path.suffix,
                }
            )

    documents.sort(key=lambda item: item["filename"])
    return documents


def sanitize_filename(filename: str) -> str:
    """Normalize a filename for safe local storage."""
    cleaned_name = Path(filename).name.strip()
    cleaned_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", cleaned_name)

    if not cleaned_name:
        raise ValueError("invalid_filename")

    return cleaned_name


def build_non_conflicting_path(filename: str) -> Path:
    """Generate a non-conflicting file path under the raw data directory."""
    sanitized_name = sanitize_filename(filename)
    candidate_path = RAW_DATA_DIR / sanitized_name

    if not candidate_path.exists():
        return candidate_path

    stem = Path(sanitized_name).stem
    suffix = Path(sanitized_name).suffix
    counter = 1

    while True:
        candidate_name = f"{stem}_{counter}{suffix}"
        candidate_path = RAW_DATA_DIR / candidate_name

        if not candidate_path.exists():
            return candidate_path

        counter += 1


def get_document_path(filename: str) -> Path:
    """Resolve a document path under the raw data directory."""
    return RAW_DATA_DIR / filename


def save_uploaded_document(filename: str, content: bytes) -> dict:
    """Persist an uploaded file to local storage."""
    file_path = build_non_conflicting_path(filename)
    file_path.write_bytes(content)

    return {
        "filename": file_path.name,
        "size_bytes": len(content),
        "saved_path": str(file_path),
    }


def read_text_document(filename: str) -> dict:
    """Read preview content for supported text-based documents."""
    file_path = get_document_path(filename)

    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(filename)

    if file_path.suffix not in TEXT_FILE_SUFFIXES:
        raise ValueError("unsupported_file_type")

    content = file_path.read_text(encoding="utf-8")

    return {
        "filename": file_path.name,
        "suffix": file_path.suffix,
        "size_bytes": file_path.stat().st_size,
        "content": content,
    }