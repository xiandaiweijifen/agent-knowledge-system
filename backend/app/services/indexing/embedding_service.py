from hashlib import sha256
import json
from pathlib import Path

from app.schemas.indexing import (
    EmbeddingRecord,
    PersistedChunkDocument,
    PersistedEmbeddingDocument,
)
from app.services.ingestion.document_service import (
    build_utc_timestamp,
    get_chunk_output_path,
    load_persisted_chunks,
)

EMBEDDING_DATA_DIR = Path("../data/embeddings")
EMBEDDING_DATA_DIR.mkdir(parents=True, exist_ok=True)
MOCK_EMBEDDING_MODEL = "mock-embedding-v1"
MOCK_VECTOR_DIM = 8
EMBEDDING_PIPELINE_VERSION = "indexing-v1"


def build_mock_embedding(text: str, vector_dim: int = MOCK_VECTOR_DIM) -> list[float]:
    """Generate a deterministic placeholder vector for pipeline scaffolding."""
    digest = sha256(text.encode("utf-8")).digest()
    vector = []

    for index in range(vector_dim):
        byte_value = digest[index]
        normalized_value = round(byte_value / 255, 6)
        vector.append(normalized_value)

    return vector


def get_embedding_output_path(filename: str) -> Path:
    """Build the output path for persisted embedding data."""
    document_name = Path(filename).stem
    return EMBEDDING_DATA_DIR / f"{document_name}.embeddings.json"


def generate_document_embeddings(filename: str) -> PersistedEmbeddingDocument:
    """Generate placeholder embeddings from persisted chunk data."""
    chunk_payload = PersistedChunkDocument.model_validate(load_persisted_chunks(filename))
    embeddings = []

    for chunk in chunk_payload.chunks:
        embeddings.append(
            EmbeddingRecord(
                embedding_id=f"{chunk.chunk_id}::embedding",
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                source_filename=chunk.source_filename,
                source_suffix=chunk.source_suffix,
                char_count=chunk.char_count,
                content=chunk.content,
                vector=build_mock_embedding(chunk.content),
            )
        )

    return PersistedEmbeddingDocument(
        filename=chunk_payload.filename,
        suffix=chunk_payload.suffix,
        source_path=chunk_payload.source_path,
        source_chunk_path=str(get_chunk_output_path(filename)),
        created_at=build_utc_timestamp(),
        pipeline_version=EMBEDDING_PIPELINE_VERSION,
        embedding_model=MOCK_EMBEDDING_MODEL,
        vector_dim=MOCK_VECTOR_DIM,
        chunk_count=chunk_payload.chunk_count,
        embeddings=embeddings,
    )


def persist_document_embeddings(filename: str) -> dict:
    """Persist placeholder embeddings for a document."""
    embedding_document = generate_document_embeddings(filename)
    output_path = get_embedding_output_path(filename)

    output_path.write_text(
        json.dumps(embedding_document.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "filename": embedding_document.filename,
        "embedding_model": embedding_document.embedding_model,
        "vector_dim": embedding_document.vector_dim,
        "embedding_count": len(embedding_document.embeddings),
        "created_at": embedding_document.created_at,
        "pipeline_version": embedding_document.pipeline_version,
        "output_path": str(output_path),
    }


def load_persisted_embeddings(filename: str) -> dict:
    """Load persisted embedding data for a document."""
    embedding_file_path = get_embedding_output_path(filename)

    if not embedding_file_path.exists() or not embedding_file_path.is_file():
        raise FileNotFoundError(filename)

    return PersistedEmbeddingDocument.model_validate_json(
        embedding_file_path.read_text(encoding="utf-8")
    ).model_dump()
