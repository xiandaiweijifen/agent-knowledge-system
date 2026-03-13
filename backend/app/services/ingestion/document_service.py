from pathlib import Path


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


def get_document_path(filename: str) -> Path:
    """Resolve a document path under the raw data directory."""
    return RAW_DATA_DIR / filename


def save_uploaded_document(filename: str, content: bytes) -> dict:
    """Persist an uploaded file to local storage."""
    file_path = get_document_path(filename)
    file_path.write_bytes(content)

    return {
        "filename": filename,
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