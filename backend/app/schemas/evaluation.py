from pydantic import BaseModel, Field


class RetrievalEvalCase(BaseModel):
    case_id: str
    filename: str
    question: str
    expected_chunk_ids: list[str] = Field(default_factory=list)


class RetrievalEvalCaseResult(BaseModel):
    case_id: str
    filename: str
    question: str
    expected_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    hit_at_k: bool
    reciprocal_rank: float


class RetrievalEvalSummary(BaseModel):
    total_cases: int
    hit_rate_at_k: float
    mean_reciprocal_rank: float


class RetrievalEvalReport(BaseModel):
    top_k: int
    summary: RetrievalEvalSummary
    cases: list[RetrievalEvalCaseResult] = Field(default_factory=list)
