from hashlib import sha256
import json
from pathlib import Path

import httpx

from app.core.config import DATA_ROOT
from app.core.config import settings
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

EMBEDDING_DATA_DIR = DATA_ROOT / "embeddings"
EMBEDDING_DATA_DIR.mkdir(parents=True, exist_ok=True)
MOCK_EMBEDDING_MODEL = "mock-embedding-v1"
MOCK_VECTOR_DIM = 8
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
GEMINI_EMBEDDINGS_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/{model_name}:batchEmbedContents"
)
EMBEDDING_PIPELINE_VERSION = "indexing-v1"


def build_mock_embedding(text: str, vector_dim: int = MOCK_VECTOR_DIM) -> list[float]:
    """Generate a deterministic placeholder vector for pipeline scaffolding."""
    digest = sha256(text.encode("utf-8")).digest()
    vector = []

    for index in range(vector_dim):
        byte_value = digest[index % len(digest)]
        normalized_value = round(byte_value / 255, 6)
        vector.append(normalized_value)

    return vector


def get_embedding_output_path(filename: str) -> Path:
    """Build the output path for persisted embedding data."""
    document_name = Path(filename).stem
    return EMBEDDING_DATA_DIR / f"{document_name}.embeddings.json"


def build_mock_embeddings(texts: list[str], vector_dim: int = MOCK_VECTOR_DIM) -> list[list[float]]:
    """Generate deterministic placeholder vectors for a batch of texts."""
    return [build_mock_embedding(text, vector_dim=vector_dim) for text in texts]


def build_openai_embeddings(
    texts: list[str],
    model_name: str | None = None,
) -> tuple[str, list[list[float]]]:
    """Generate embeddings from OpenAI for a batch of texts."""
    resolved_model_name = model_name or settings.openai_embedding_model
    payload = {
        "model": resolved_model_name,
        "input": texts,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    response = httpx.post(
        OPENAI_EMBEDDINGS_URL,
        headers=headers,
        json=payload,
        timeout=30.0,
    )
    response.raise_for_status()
    response_payload = response.json()
    embedding_items = sorted(response_payload["data"], key=lambda item: item["index"])
    vectors = [item["embedding"] for item in embedding_items]

    return resolved_model_name, vectors


def build_gemini_embeddings(
    texts: list[str],
    model_name: str | None = None,
) -> tuple[str, list[list[float]]]:
    """Generate embeddings from Gemini for a batch of texts."""
    resolved_model_name = model_name or settings.gemini_embedding_model
    request_items = []

    for text in texts:
        request_items.append(
            {
                "model": f"models/{resolved_model_name}",
                "content": {
                    "parts": [
                        {
                            "text": text,
                        }
                    ]
                },
            }
        )

    response = httpx.post(
        GEMINI_EMBEDDINGS_URL_TEMPLATE.format(
            model_name=resolved_model_name,
        ),
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={"requests": request_items},
        timeout=30.0,
    )
    response.raise_for_status()
    response_payload = response.json()
    vectors = [item["values"] for item in response_payload["embeddings"]]

    return resolved_model_name, vectors


def generate_embedding_vectors(texts: list[str]) -> tuple[str, str, list[list[float]]]:
    """Generate vectors with a real provider when available, otherwise fallback."""
    if not texts:
        return "mock", MOCK_EMBEDDING_MODEL, []

    provider = settings.embedding_provider.lower().strip()

    if provider == "mock":
        return "mock", MOCK_EMBEDDING_MODEL, build_mock_embeddings(texts)

    if provider == "gemini":
        if not settings.gemini_api_key:
            return "mock_fallback", MOCK_EMBEDDING_MODEL, build_mock_embeddings(texts)

        try:
            model_name, vectors = build_gemini_embeddings(texts)
            return "gemini", model_name, vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return "mock_fallback", MOCK_EMBEDDING_MODEL, build_mock_embeddings(texts)

    if provider == "openai":
        if not settings.openai_api_key:
            return "mock_fallback", MOCK_EMBEDDING_MODEL, build_mock_embeddings(texts)

        try:
            model_name, vectors = build_openai_embeddings(texts)
            return "openai", model_name, vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return "mock_fallback", MOCK_EMBEDDING_MODEL, build_mock_embeddings(texts)

    raise ValueError("unsupported_embedding_provider")


def generate_query_embedding(
    question: str,
    embedding_provider: str,
    embedding_model: str,
    vector_dim: int,
) -> tuple[str, str, list[float]]:
    """Generate a query embedding that matches the persisted document provider."""
    normalized_provider = embedding_provider.strip().lower()

    if normalized_provider in {"mock", "mock_fallback"}:
        return "mock", MOCK_EMBEDDING_MODEL, build_mock_embedding(
            question,
            vector_dim=vector_dim,
        )

    if normalized_provider == "openai":
        if not settings.openai_api_key:
            return "mock_fallback", MOCK_EMBEDDING_MODEL, build_mock_embedding(
                question,
                vector_dim=vector_dim,
            )

        try:
            _, vectors = build_openai_embeddings([question], model_name=embedding_model)
            return "openai", embedding_model, vectors[0]
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError):
            return "mock_fallback", MOCK_EMBEDDING_MODEL, build_mock_embedding(
                question,
                vector_dim=vector_dim,
            )

    if normalized_provider == "gemini":
        if not settings.gemini_api_key:
            return "mock_fallback", MOCK_EMBEDDING_MODEL, build_mock_embedding(
                question,
                vector_dim=vector_dim,
            )

        try:
            _, vectors = build_gemini_embeddings([question], model_name=embedding_model)
            return "gemini", embedding_model, vectors[0]
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError):
            return "mock_fallback", MOCK_EMBEDDING_MODEL, build_mock_embedding(
                question,
                vector_dim=vector_dim,
            )

    return "mock_fallback", MOCK_EMBEDDING_MODEL, build_mock_embedding(
        question,
        vector_dim=vector_dim,
    )


def generate_document_embeddings(filename: str) -> PersistedEmbeddingDocument:
    """Generate embeddings from persisted chunk data."""
    chunk_payload = PersistedChunkDocument.model_validate(load_persisted_chunks(filename))
    chunk_texts = [chunk.content for chunk in chunk_payload.chunks]
    embedding_provider, embedding_model, vectors = generate_embedding_vectors(chunk_texts)
    embeddings = []

    for chunk, vector in zip(chunk_payload.chunks, vectors):
        embeddings.append(
            EmbeddingRecord(
                embedding_id=f"{chunk.chunk_id}::embedding",
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                source_filename=chunk.source_filename,
                source_suffix=chunk.source_suffix,
                char_count=chunk.char_count,
                content=chunk.content,
                vector=vector,
            )
        )

    vector_dim = len(vectors[0]) if vectors else 0

    return PersistedEmbeddingDocument(
        filename=chunk_payload.filename,
        suffix=chunk_payload.suffix,
        source_path=chunk_payload.source_path,
        source_chunk_path=str(get_chunk_output_path(filename)),
        created_at=build_utc_timestamp(),
        pipeline_version=EMBEDDING_PIPELINE_VERSION,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        vector_dim=vector_dim,
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
        "embedding_provider": embedding_document.embedding_provider,
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
