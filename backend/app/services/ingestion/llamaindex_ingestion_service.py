"""
LlamaIndex-based ingestion service.

Reads already-chunked data from the existing pipeline and builds a
VectorStoreIndex backed by SimpleVectorStore (file-persisted).

This runs alongside the existing JSON embedding pipeline so both
retrieval paths are available during the transition.  Package 6 will
switch the query route to use this index exclusively.

Storage layout:
    data/llamaindex_store/<document_stem>/
        docstore.json
        vector_store.json
        index_store.json
        graph_store.json
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from llama_index.core import (
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import TextNode

from app.core.config import DATA_ROOT
from app.services.indexing.embedding_service import (
    generate_embedding_vectors,
    generate_query_embedding,
)
from app.services.ingestion.document_service import load_persisted_chunks

logger = logging.getLogger(__name__)

LLAMAINDEX_STORE_DIR = DATA_ROOT / "llamaindex_store"
LLAMAINDEX_STORE_DIR.mkdir(parents=True, exist_ok=True)


def get_llamaindex_store_path(filename: str) -> Path:
    stem = Path(filename).stem
    path = LLAMAINDEX_STORE_DIR / stem
    path.mkdir(parents=True, exist_ok=True)
    return path


def has_llamaindex_index(filename: str) -> bool:
    path = LLAMAINDEX_STORE_DIR / Path(filename).stem
    if not path.exists() or not path.is_dir():
        return False

    required_files = {
        "docstore.json",
        "index_store.json",
        "vector_store.json",
    }
    present_files = {item.name for item in path.iterdir() if item.is_file()}
    return required_files.issubset(present_files)


# ---------------------------------------------------------------------------
# Custom embedding adapter — wraps the existing provider-agnostic service
# so LlamaIndex uses the same Gemini / OpenAI / mock logic already in place.
# ---------------------------------------------------------------------------

class ProjectEmbedding(BaseEmbedding):
    """
    Thin adapter that delegates to the project's existing
    generate_embedding_vectors() / generate_query_embedding() functions.
    """

    # Pydantic fields inherited from BaseEmbedding cover model_name etc.
    # We only need to implement the three abstract methods below.

    def _get_query_embedding(self, query: str) -> list[float]:
        # provider/model stored in the persisted embedding doc; here we use
        # whatever the current settings dictate for a fresh query.
        _, _, vector = generate_embedding_vectors([query])
        return vector[0] if vector else []

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        _, _, vectors = generate_embedding_vectors([text])
        return vectors[0] if vectors else []

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        _, _, vectors = generate_embedding_vectors(texts)
        return vectors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_llamaindex_index(filename: str) -> dict[str, Any]:
    """
    Build (or rebuild) a VectorStoreIndex from persisted chunks for a document.

    Reads chunk data from the existing JSON pipeline, creates LlamaIndex
    TextNode objects, builds a VectorStoreIndex, and persists it to disk.

    Returns a summary dict with node count and store path.
    """
    raw_chunks = load_persisted_chunks(filename)
    chunks = raw_chunks.get("chunks", [])

    if not chunks:
        raise ValueError("no_chunks_found")

    nodes = [
        TextNode(
            text=chunk["content"],
            id_=chunk["chunk_id"],
            metadata={
                "chunk_index": chunk["chunk_index"],
                "source_filename": chunk.get("source_filename", filename),
                "source_suffix": chunk.get("source_suffix", ""),
                "char_count": chunk.get("char_count", len(chunk["content"])),
                "section_title": chunk.get("section_title", ""),
                "section_path": chunk.get("section_path", []),
                "heading_level": chunk.get("heading_level"),
            },
        )
        for chunk in chunks
    ]

    embed_model = ProjectEmbedding()
    storage_context = StorageContext.from_defaults()

    index = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=False,
    )

    persist_dir = str(get_llamaindex_store_path(filename))
    index.storage_context.persist(persist_dir=persist_dir)

    logger.info(
        "LlamaIndex index built for %s — %d nodes → %s",
        filename, len(nodes), persist_dir,
    )

    return {
        "filename": filename,
        "node_count": len(nodes),
        "store_path": persist_dir,
    }


def load_llamaindex_index(filename: str) -> VectorStoreIndex:
    """Load a previously persisted VectorStoreIndex from disk."""
    persist_dir = str(get_llamaindex_store_path(filename))
    storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
    return load_index_from_storage(
        storage_context,
        embed_model=ProjectEmbedding(),
    )


def query_llamaindex_index(
    filename: str,
    query_text: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """
    Query a persisted LlamaIndex index and return ranked matches.

    Returns a list of dicts with keys: chunk_id, content, score, metadata.
    """
    index = load_llamaindex_index(filename)
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query_text)

    return [
        {
            "chunk_id": node.node.id_,
            "content": node.node.get_content(),
            "score": round(node.score or 0.0, 6),
            "metadata": node.node.metadata,
        }
        for node in nodes
    ]
