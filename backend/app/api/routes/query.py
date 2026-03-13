from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.agent.query_service import run_query

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    filename: str
    question: str
    top_k: int = 3


@router.post("/query")
def query_knowledge(request: QueryRequest):
    try:
        return run_query(
            filename=request.filename,
            question=request.question,
            top_k=request.top_k,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Persisted embedding file not found. Generate embeddings first",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
