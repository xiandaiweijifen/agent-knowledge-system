from typing import Any

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
    clarification_context: dict[str, str] = Field(default_factory=dict)
    resume_via_run_id: bool = False
    expected_route_type: str
    expected_workflow_status: str
    expected_question: str | None = None
    expected_resume_trace: bool | None = None
    expected_tool_chain_length: int | None = None
    expected_final_tool_name: str | None = None
    expected_final_action: str | None = None
    expected_final_output_keys: list[str] = Field(default_factory=list)


class AgentWorkflowEvalCaseResult(BaseModel):
    case_id: str
    question: str
    actual_question: str = ""
    filename: str | None = None
    expected_route_type: str
    actual_route_type: str
    expected_workflow_status: str
    actual_workflow_status: str
    route_reason: str
    matched: bool
    expected_question: str | None = None
    expected_resume_trace: bool | None = None
    resume_trace_present: bool = False
    expected_tool_chain_length: int | None = None
    actual_tool_chain_length: int = 0
    expected_final_tool_name: str | None = None
    actual_final_tool_name: str | None = None
    expected_final_action: str | None = None
    actual_final_action: str | None = None
    final_output_key_matches: dict[str, bool] = Field(default_factory=dict)


class AgentWorkflowEvalSummary(BaseModel):
    total_cases: int
    workflow_accuracy: float


class AgentWorkflowEvalReport(BaseModel):
    summary: AgentWorkflowEvalSummary
    cases: list[AgentWorkflowEvalCaseResult] = Field(default_factory=list)


class ToolExecutionEvalCase(BaseModel):
    case_id: str
    question: str
    expected_tool_name: str
    expected_action: str
    expected_execution_status: str = "completed"
    expected_arguments: dict[str, str] = Field(default_factory=dict)
    expected_output: dict[str, Any] = Field(default_factory=dict)
    expected_output_keys: list[str] = Field(default_factory=list)


class ToolExecutionEvalCaseResult(BaseModel):
    case_id: str
    question: str
    expected_tool_name: str
    actual_tool_name: str
    expected_action: str
    actual_action: str
    expected_execution_status: str
    actual_execution_status: str
    matched: bool
    argument_matches: dict[str, bool] = Field(default_factory=dict)
    output_matches: dict[str, bool] = Field(default_factory=dict)
    output_key_matches: dict[str, bool] = Field(default_factory=dict)


class ToolExecutionEvalSummary(BaseModel):
    total_cases: int
    tool_accuracy: float


class ToolExecutionEvalReport(BaseModel):
    summary: ToolExecutionEvalSummary
    cases: list[ToolExecutionEvalCaseResult] = Field(default_factory=list)
