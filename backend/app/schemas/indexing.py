from pydantic import BaseModel, Field


class ChunkRecord(BaseModel):
    chunk_id: str
    chunk_index: int
    source_filename: str
    source_suffix: str
    start_char: int
    end_char: int
    char_count: int
    content: str


class PersistedChunkDocument(BaseModel):
    filename: str
    suffix: str
    size_bytes: int
    source_path: str = ""
    created_at: str = ""
    pipeline_version: str = ""
    chunk_strategy: str = "character"
    chunk_count: int
    chunk_size: int
    chunk_overlap: int
    chunks: list[ChunkRecord] = Field(default_factory=list)


class EmbeddingRecord(BaseModel):
    embedding_id: str
    chunk_id: str
    chunk_index: int
    source_filename: str
    source_suffix: str
    char_count: int
    content: str
    vector: list[float] = Field(default_factory=list)


class PersistedEmbeddingDocument(BaseModel):
    filename: str
    suffix: str
    source_path: str = ""
    source_chunk_path: str = ""
    created_at: str = ""
    pipeline_version: str = ""
    embedding_provider: str = ""
    embedding_model: str
    vector_dim: int
    chunk_count: int
    embeddings: list[EmbeddingRecord] = Field(default_factory=list)
