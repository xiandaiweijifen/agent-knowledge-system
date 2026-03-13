from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.retrieval.retrieval_service import retrieve_relevant_chunks

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    filename: str
    question: str
    top_k: int = 3


@router.post("/query")
def query_knowledge(request: QueryRequest):
    try:
        retrieval_result = retrieve_relevant_chunks(
            filename=request.filename,
            query_text=request.question,
            top_k=request.top_k,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Persisted embedding file not found. Generate embeddings first",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "filename": retrieval_result["filename"],
        "question": retrieval_result["question"],
        "answer": "Retrieval completed. LLM answer generation is not implemented yet",
        "retrieval": retrieval_result,
    }
