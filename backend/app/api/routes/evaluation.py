from fastapi import APIRouter, HTTPException

from app.schemas.evaluation_api import (
    RetrievalEvalDatasetListResponse,
    RetrievalEvalRequest,
    RetrievalEvalResponse,
)
from app.services.evaluation import retrieval_eval_service

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation/retrieval/datasets", response_model=RetrievalEvalDatasetListResponse)
def get_retrieval_datasets() -> RetrievalEvalDatasetListResponse:
    return RetrievalEvalDatasetListResponse(
        datasets=retrieval_eval_service.list_retrieval_datasets(),
    )


@router.post("/evaluation/retrieval", response_model=RetrievalEvalResponse)
def evaluate_retrieval(request: RetrievalEvalRequest) -> RetrievalEvalResponse:
    try:
        report = retrieval_eval_service.evaluate_named_retrieval_dataset(
            dataset_name=request.dataset_name,
            top_k=request.top_k,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation dataset not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return RetrievalEvalResponse(
        dataset_name=request.dataset_name,
        report=report,
    )
