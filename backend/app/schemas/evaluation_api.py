from pydantic import BaseModel

from app.schemas.evaluation import AgentRouteEvalReport, RetrievalEvalReport


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
