from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    filename: str
    question: str
    top_k: int = 3


class RetrievedChunkMatch(BaseModel):
    chunk_id: str
    chunk_index: int
    source_filename: str
    source_suffix: str
    char_count: int
    content: str
    score: float


class RetrievalResult(BaseModel):
    filename: str
    embedding_model: str
    question: str
    top_k: int
    matches: list[RetrievedChunkMatch] = Field(default_factory=list)


class QueryResponse(BaseModel):
    filename: str
    question: str
    answer: str
    answer_source: str
    model: str
    retrieval: RetrievalResult
