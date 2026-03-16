from fastapi import APIRouter, HTTPException

from app.schemas.query import (
    AgentRecoverRequest,
    AgentQueryRequest,
    AgentWorkflowMigrationResponse,
    AgentWorkflowRunPruneRequest,
    AgentWorkflowRunPruneResponse,
    AgentResumeRequest,
    AgentWorkflowResponse,
    AgentWorkflowRunListResponse,
    AgentWorkflowRunResetRequest,
    AgentWorkflowRunResetResponse,
    AgentWorkflowRunStatsResponse,
    QueryDiagnosticsRequest,
    QueryDiagnosticsResponse,
    QueryRequest,
    QueryRouteRequest,
    QueryResponse,
    RouteDecision,
)
from app.services.agent.orchestrator_service import (
    get_persisted_workflow_run,
    get_workflow_run_stats,
    list_persisted_workflow_runs,
    migrate_persisted_workflow_runs,
    orchestrate_agent_request,
    prune_persisted_workflow_runs,
    recover_agent_request,
    reset_persisted_workflow_runs,
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
            debug_fault_injection=request.debug_fault_injection,
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
            debug_fault_injection=request.debug_fault_injection,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Persisted embedding file not found. Generate embeddings first",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/query/agent/recover", response_model=AgentWorkflowResponse)
def recover_agent_query(request: AgentRecoverRequest) -> AgentWorkflowResponse:
    try:
        return recover_agent_request(
            run_id=request.run_id,
            recovery_action=request.recovery_action,
            clarification_context=request.clarification_context,
            filename=request.filename,
            top_k=request.top_k,
            debug_fault_injection=request.debug_fault_injection,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/query/agent/runs", response_model=AgentWorkflowRunListResponse)
def list_agent_workflow_runs(limit: int = 20) -> AgentWorkflowRunListResponse:
    try:
        return list_persisted_workflow_runs(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/query/agent/runs/migrate", response_model=AgentWorkflowMigrationResponse)
def migrate_agent_workflow_runs() -> AgentWorkflowMigrationResponse:
    return migrate_persisted_workflow_runs()


@router.get("/query/agent/runs/stats", response_model=AgentWorkflowRunStatsResponse)
def get_agent_workflow_run_stats() -> AgentWorkflowRunStatsResponse:
    return get_workflow_run_stats()


@router.post("/query/agent/runs/prune", response_model=AgentWorkflowRunPruneResponse)
def prune_agent_workflow_runs(
    request: AgentWorkflowRunPruneRequest,
) -> AgentWorkflowRunPruneResponse:
    try:
        return prune_persisted_workflow_runs(request.retain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/query/agent/runs/reset", response_model=AgentWorkflowRunResetResponse)
def reset_agent_workflow_runs(
    request: AgentWorkflowRunResetRequest,
) -> AgentWorkflowRunResetResponse:
    try:
        return reset_persisted_workflow_runs(request.confirm)
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
