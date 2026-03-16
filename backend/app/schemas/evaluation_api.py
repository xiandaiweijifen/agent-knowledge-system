from pydantic import BaseModel

from app.schemas.evaluation import (
    AgentRouteEvalReport,
    AgentWorkflowEvalReport,
    RetrievalEvalReport,
    ToolExecutionEvalReport,
)


class EvaluationReportMetadata(BaseModel):
    saved_at: str | None = None
    report_source: str | None = None


class EvaluationReportHistoryEntry(BaseModel):
    dataset_name: str
    saved_at: str
    report_source: str = "saved"
    top_k: int | None = None
    primary_metric_name: str
    primary_metric_value: float
    case_count: int


class EvaluationReportHistoryResponse(BaseModel):
    entries: list[EvaluationReportHistoryEntry]


class RetrievalEvalDatasetInfo(BaseModel):
    dataset_name: str
    case_count: int
    filenames: list[str]


class RetrievalEvalRequest(BaseModel):
    dataset_name: str
    top_k: int = 3


class RetrievalEvalResponse(EvaluationReportMetadata):
    dataset_name: str
    report: RetrievalEvalReport


class RetrievalEvalDatasetListResponse(BaseModel):
    datasets: list[RetrievalEvalDatasetInfo]


class AgentRouteEvalDatasetInfo(BaseModel):
    dataset_name: str
    case_count: int


class AgentRouteEvalRequest(BaseModel):
    dataset_name: str


class AgentRouteEvalResponse(EvaluationReportMetadata):
    dataset_name: str
    report: AgentRouteEvalReport


class AgentRouteEvalDatasetListResponse(BaseModel):
    datasets: list[AgentRouteEvalDatasetInfo]


class AgentWorkflowEvalDatasetInfo(BaseModel):
    dataset_name: str
    case_count: int


class AgentWorkflowEvalRequest(BaseModel):
    dataset_name: str


class AgentWorkflowEvalResponse(EvaluationReportMetadata):
    dataset_name: str
    report: AgentWorkflowEvalReport


class AgentWorkflowEvalDatasetListResponse(BaseModel):
    datasets: list[AgentWorkflowEvalDatasetInfo]


class ToolExecutionEvalDatasetInfo(BaseModel):
    dataset_name: str
    case_count: int


class ToolExecutionEvalRequest(BaseModel):
    dataset_name: str


class ToolExecutionEvalResponse(EvaluationReportMetadata):
    dataset_name: str
    report: ToolExecutionEvalReport


class ToolExecutionEvalDatasetListResponse(BaseModel):
    datasets: list[ToolExecutionEvalDatasetInfo]


class EvaluationOverviewRetrievalSummary(BaseModel):
    dataset_count: int
    total_cases: int
    mean_hit_rate_at_k: float
    mean_reciprocal_rank: float
    best_dataset_name: str | None = None
    best_hit_rate_at_k: float = 0.0


class EvaluationOverviewWorkflowSummary(BaseModel):
    total_run_count: int
    completed_run_count: int
    clarification_required_run_count: int
    failed_run_count: int
    completion_rate: float
    clarification_rate: float
    failed_rate: float


class EvaluationOverviewRecoverySummary(BaseModel):
    recovered_run_count: int
    recovered_completed_run_count: int
    recovery_success_rate: float
    average_recovery_depth: float
    resume_from_failed_step_count: int
    manual_retrigger_count: int
    clarification_recovery_count: int


class EvaluationOverviewResponse(BaseModel):
    generated_at: str
    cache_status: str = "fresh"
    retrieval: EvaluationOverviewRetrievalSummary
    workflow: EvaluationOverviewWorkflowSummary
    recovery: EvaluationOverviewRecoverySummary
