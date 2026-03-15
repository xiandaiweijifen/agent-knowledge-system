from fastapi import APIRouter, HTTPException

from app.schemas.query import (
    AgentQueryRequest,
    AgentResumeRequest,
    AgentWorkflowResponse,
    AgentWorkflowRunListResponse,
    QueryDiagnosticsRequest,
    QueryDiagnosticsResponse,
    QueryRequest,
    QueryRouteRequest,
    QueryResponse,
    RouteDecision,
)
from app.services.agent.orchestrator_service import (
    get_persisted_workflow_run,
    list_persisted_workflow_runs,
    orchestrate_agent_request,
    resume_agent_request,
)
from app.schemas.tools import (
    ToolCatalogResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolPlanRequest,
    ToolPlanResponse,
)
from app.services.agent.router_service import route_request
from app.services.agent.tool_service import (
    execute_tool_request,
    list_registered_tools,
    plan_tool_request,
)
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


@router.post("/query/agent", response_model=AgentWorkflowResponse)
def orchestrate_agent_query(request: AgentQueryRequest) -> AgentWorkflowResponse:
    try:
        return orchestrate_agent_request(
            question=request.question,
            filename=request.filename,
            top_k=request.top_k,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Persisted embedding file not found. Generate embeddings first",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/query/agent/resume", response_model=AgentWorkflowResponse)
def resume_agent_query(request: AgentResumeRequest) -> AgentWorkflowResponse:
    try:
        return resume_agent_request(
            original_question=request.original_question,
            clarification_context=request.clarification_context,
            run_id=request.run_id,
            filename=request.filename,
            top_k=request.top_k,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Persisted embedding file not found. Generate embeddings first",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/query/agent/runs", response_model=AgentWorkflowRunListResponse)
def list_agent_workflow_runs(limit: int = 20) -> AgentWorkflowRunListResponse:
    try:
        return list_persisted_workflow_runs(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/query/agent/runs/{run_id}", response_model=AgentWorkflowResponse)
def get_agent_workflow_run(run_id: str) -> AgentWorkflowResponse:
    try:
        return get_persisted_workflow_run(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/query/tools/execute", response_model=ToolExecutionResponse)
def execute_query_tool(request: ToolExecutionRequest) -> ToolExecutionResponse:
    try:
        return execute_tool_request(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/query/tools", response_model=ToolCatalogResponse)
def get_query_tools() -> ToolCatalogResponse:
    return list_registered_tools()


@router.post("/query/tools/plan", response_model=ToolPlanResponse)
def plan_query_tool(request: ToolPlanRequest) -> ToolPlanResponse:
    try:
        return plan_tool_request(request.question)
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
