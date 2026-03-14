from pydantic import BaseModel

from app.schemas.evaluation import RetrievalEvalReport


class RetrievalEvalRequest(BaseModel):
    dataset_name: str
    top_k: int = 3


class RetrievalEvalResponse(BaseModel):
    dataset_name: str
    report: RetrievalEvalReport
