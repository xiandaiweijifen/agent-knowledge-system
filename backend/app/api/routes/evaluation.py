from fastapi import APIRouter, HTTPException

from app.schemas.evaluation_api import RetrievalEvalRequest, RetrievalEvalResponse
from app.services.evaluation.retrieval_eval_service import evaluate_named_retrieval_dataset

router = APIRouter(tags=["evaluation"])


@router.post("/evaluation/retrieval", response_model=RetrievalEvalResponse)
def evaluate_retrieval(request: RetrievalEvalRequest) -> RetrievalEvalResponse:
    try:
        report = evaluate_named_retrieval_dataset(
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
