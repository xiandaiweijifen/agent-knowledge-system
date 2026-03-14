from fastapi import APIRouter, HTTPException

from app.schemas.query import (
    QueryDiagnosticsRequest,
    QueryDiagnosticsResponse,
    QueryRequest,
    QueryRouteRequest,
    QueryResponse,
    RouteDecision,
)
from app.services.agent.router_service import route_request
from app.services.agent.query_service import run_query
from app.services.retrieval.retrieval_service import retrieve_relevant_chunks_with_diagnostics

router = APIRouter(tags=["query"])


@router.post("/query/route", response_model=RouteDecision)
def route_query_request(request: QueryRouteRequest) -> RouteDecision:
    try:
        return route_request(
            question=request.question,
            filename=request.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/query", response_model=QueryResponse)
def query_knowledge(request: QueryRequest) -> QueryResponse:
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


@router.post("/query/diagnostics", response_model=QueryDiagnosticsResponse)
def query_diagnostics(request: QueryDiagnosticsRequest) -> QueryDiagnosticsResponse:
    try:
        return retrieve_relevant_chunks_with_diagnostics(
            filename=request.filename,
            query_text=request.question,
            top_k=request.top_k,
            candidate_count=request.candidate_count,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Persisted embedding file not found. Generate embeddings first",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
