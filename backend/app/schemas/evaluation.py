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


class AgentRouteEvalCase(BaseModel):
    case_id: str
    question: str
    filename: str | None = None
    expected_route_type: str


class AgentRouteEvalCaseResult(BaseModel):
    case_id: str
    question: str
    filename: str | None = None
    expected_route_type: str
    actual_route_type: str
    route_reason: str
    matched: bool


class AgentRouteEvalSummary(BaseModel):
    total_cases: int
    route_accuracy: float


class AgentRouteEvalReport(BaseModel):
    summary: AgentRouteEvalSummary
    cases: list[AgentRouteEvalCaseResult] = Field(default_factory=list)


class AgentWorkflowEvalCase(BaseModel):
    case_id: str
    question: str
    filename: str | None = None
    top_k: int = 3
    expected_route_type: str
    expected_workflow_status: str


class AgentWorkflowEvalCaseResult(BaseModel):
    case_id: str
    question: str
    filename: str | None = None
    expected_route_type: str
    actual_route_type: str
    expected_workflow_status: str
    actual_workflow_status: str
    route_reason: str
    matched: bool


class AgentWorkflowEvalSummary(BaseModel):
    total_cases: int
    workflow_accuracy: float


class AgentWorkflowEvalReport(BaseModel):
    summary: AgentWorkflowEvalSummary
    cases: list[AgentWorkflowEvalCaseResult] = Field(default_factory=list)
