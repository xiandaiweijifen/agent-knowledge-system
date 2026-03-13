from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    question: str


@router.post("/query")
def query_knowledge(request: QueryRequest):
    return {
        "question": request.question,
        "answer": "Query endpoint ready"
    }