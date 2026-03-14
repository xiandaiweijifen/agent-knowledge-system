from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    filename: str
    question: str
    top_k: int = 3


class QueryDiagnosticsRequest(BaseModel):
    filename: str
    question: str
    top_k: int = 3
    candidate_count: int = 10


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
    embedding_provider: str
    embedding_model: str
    vector_dim: int
    question: str
    top_k: int
    retrieved_at: str
    retrieval_latency_ms: float
    query_embedding_provider: str
    query_embedding_model: str
    matches: list[RetrievedChunkMatch] = Field(default_factory=list)


class QueryResponse(BaseModel):
    filename: str
    question: str
    answer: str
    answer_source: str
    model: str
    answered_at: str
    answer_latency_ms: float
    chat_provider: str
    chat_model: str
    retrieval: RetrievalResult


class RetrievalDiagnosticsSummary(BaseModel):
    total_scored_chunks: int
    returned_candidate_count: int
    max_score: float
    min_score: float
    mean_score: float


class QueryDiagnosticsResponse(BaseModel):
    filename: str
    question: str
    retrieval: RetrievalResult
    diagnostics: RetrievalDiagnosticsSummary
    candidates: list[RetrievedChunkMatch] = Field(default_factory=list)
