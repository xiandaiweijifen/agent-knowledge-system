from pathlib import Path
from datetime import datetime, UTC
import re
import json

from app.core.config import DATA_ROOT
from app.services.ingestion.text_extractor import extract_text_from_file
from app.services.ingestion.chunker import chunk_text

RAW_DATA_DIR = DATA_ROOT / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
CHUNK_DATA_DIR = DATA_ROOT / "chunks"
CHUNK_DATA_DIR.mkdir(parents=True, exist_ok=True)
LISTABLE_DOCUMENT_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}
CHUNK_PIPELINE_VERSION = "ingestion-v1"


def list_documents() -> list[dict]:
    """Return basic metadata for all uploaded documents."""
    documents = []

    for file_path in RAW_DATA_DIR.iterdir():
        if not file_path.is_file():
            continue

        if file_path.name.startswith("."):
            continue

        if file_path.suffix.lower() not in LISTABLE_DOCUMENT_SUFFIXES:
            continue

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

    content = extract_text_from_file(file_path)

    return {
        "filename": file_path.name,
        "suffix": file_path.suffix,
        "size_bytes": file_path.stat().st_size,
        "content": content,
    }


def chunk_document(filename: str, chunk_size: int = 500, chunk_overlap: int = 100) -> dict:
    """Load a text document and split it into retrievable chunks."""
    return chunk_document_with_strategy(
        filename=filename,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunk_strategy="character",
    )


def chunk_document_with_strategy(
    filename: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    chunk_strategy: str = "character",
) -> dict:
    """Load a text document and split it into retrievable chunks."""
    document = read_text_document(filename)
    chunks = chunk_text(
        text=document["content"],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunk_strategy=chunk_strategy,
        source_filename=document["filename"],
        source_suffix=document["suffix"],
    )

    return {
        "filename": document["filename"],
        "suffix": document["suffix"],
        "size_bytes": document["size_bytes"],
        "chunk_strategy": chunk_strategy,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def get_chunk_output_path(filename: str) -> Path:
    """Build the output path for persisted chunk data."""
    document_name = Path(filename).stem
    return CHUNK_DATA_DIR / f"{document_name}.chunks.json"


def build_utc_timestamp() -> str:
    """Return a UTC timestamp for persisted pipeline artifacts."""
    return datetime.now(UTC).isoformat()


def persist_document_chunks(
    filename: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    chunk_strategy: str = "character",
) -> dict:
    """Generate chunks for a document and persist them as JSON."""
    chunked_document = chunk_document_with_strategy(
        filename=filename,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunk_strategy=chunk_strategy,
    )

    output_path = get_chunk_output_path(filename)

    output_payload = {
        "filename": chunked_document["filename"],
        "suffix": chunked_document["suffix"],
        "size_bytes": chunked_document["size_bytes"],
        "source_path": str(get_document_path(filename)),
        "created_at": build_utc_timestamp(),
        "pipeline_version": CHUNK_PIPELINE_VERSION,
        "chunk_strategy": chunk_strategy,
        "chunk_count": chunked_document["chunk_count"],
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "chunks": chunked_document["chunks"],
    }

    output_path.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "filename": chunked_document["filename"],
        "chunk_strategy": chunk_strategy,
        "chunk_count": chunked_document["chunk_count"],
        "output_path": str(output_path),
    }


def load_persisted_chunks(filename: str) -> dict:
    """Load persisted chunk data for a document."""
    chunk_file_path = get_chunk_output_path(filename)

    if not chunk_file_path.exists() or not chunk_file_path.is_file():
        raise FileNotFoundError(filename)

    return json.loads(chunk_file_path.read_text(encoding="utf-8"))


def delete_document_with_artifacts(filename: str) -> dict:
    """Delete a raw document and its persisted chunk and embedding artifacts."""
    document_path = get_document_path(filename)

    if not document_path.exists() or not document_path.is_file():
        raise FileNotFoundError(filename)

    chunk_path = get_chunk_output_path(filename)

    # Avoid top-level import cycles with the indexing service.
    from app.services.indexing.embedding_service import get_embedding_output_path

    embedding_path = get_embedding_output_path(filename)

    document_path.unlink()

    deleted_chunks = False
    if chunk_path.exists() and chunk_path.is_file():
        chunk_path.unlink()
        deleted_chunks = True

    deleted_embeddings = False
    if embedding_path.exists() and embedding_path.is_file():
        embedding_path.unlink()
        deleted_embeddings = True

    return {
        "filename": filename,
        "deleted_document": True,
        "deleted_chunks": deleted_chunks,
        "deleted_embeddings": deleted_embeddings,
    }
