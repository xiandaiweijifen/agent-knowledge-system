from pydantic import BaseModel

from app.schemas.evaluation import (
    AgentRouteEvalReport,
    AgentWorkflowEvalReport,
    RetrievalEvalReport,
    ToolExecutionEvalReport,
)


class RetrievalEvalDatasetInfo(BaseModel):
    dataset_name: str
    case_count: int
    filenames: list[str]


class RetrievalEvalRequest(BaseModel):
    dataset_name: str
    top_k: int = 3


class RetrievalEvalResponse(BaseModel):
    dataset_name: str
    report: RetrievalEvalReport


class RetrievalEvalDatasetListResponse(BaseModel):
    datasets: list[RetrievalEvalDatasetInfo]


class AgentRouteEvalDatasetInfo(BaseModel):
    dataset_name: str
    case_count: int


class AgentRouteEvalRequest(BaseModel):
    dataset_name: str


class AgentRouteEvalResponse(BaseModel):
    dataset_name: str
    report: AgentRouteEvalReport


class AgentRouteEvalDatasetListResponse(BaseModel):
    datasets: list[AgentRouteEvalDatasetInfo]


class AgentWorkflowEvalDatasetInfo(BaseModel):
    dataset_name: str
    case_count: int


class AgentWorkflowEvalRequest(BaseModel):
    dataset_name: str


class AgentWorkflowEvalResponse(BaseModel):
    dataset_name: str
    report: AgentWorkflowEvalReport


class AgentWorkflowEvalDatasetListResponse(BaseModel):
    datasets: list[AgentWorkflowEvalDatasetInfo]


class ToolExecutionEvalDatasetInfo(BaseModel):
    dataset_name: str
    case_count: int


class ToolExecutionEvalRequest(BaseModel):
    dataset_name: str


class ToolExecutionEvalResponse(BaseModel):
    dataset_name: str
    report: ToolExecutionEvalReport


class ToolExecutionEvalDatasetListResponse(BaseModel):
    datasets: list[ToolExecutionEvalDatasetInfo]
