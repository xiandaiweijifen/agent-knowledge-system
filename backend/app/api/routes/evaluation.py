from fastapi import APIRouter, HTTPException

from app.schemas.evaluation_api import (
    AgentRouteEvalDatasetListResponse,
    AgentRouteEvalRequest,
    AgentRouteEvalResponse,
    EvaluationOverviewResponse,
    ToolExecutionEvalDatasetListResponse,
    ToolExecutionEvalRequest,
    ToolExecutionEvalResponse,
    AgentWorkflowEvalDatasetListResponse,
    AgentWorkflowEvalRequest,
    AgentWorkflowEvalResponse,
    RetrievalEvalDatasetListResponse,
    RetrievalEvalRequest,
    RetrievalEvalResponse,
)
from app.services.evaluation import (
    agent_route_eval_service,
    tool_execution_eval_service,
    agent_workflow_eval_service,
    overview_service,
    retrieval_eval_service,
)

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation/overview", response_model=EvaluationOverviewResponse)
def get_evaluation_overview() -> EvaluationOverviewResponse:
    return overview_service.get_evaluation_overview()


@router.get("/evaluation/retrieval/datasets", response_model=RetrievalEvalDatasetListResponse)
def get_retrieval_datasets() -> RetrievalEvalDatasetListResponse:
    return RetrievalEvalDatasetListResponse(
        datasets=retrieval_eval_service.list_retrieval_datasets(),
    )


@router.get("/evaluation/agent-route/datasets", response_model=AgentRouteEvalDatasetListResponse)
def get_agent_route_datasets() -> AgentRouteEvalDatasetListResponse:
    return AgentRouteEvalDatasetListResponse(
        datasets=agent_route_eval_service.list_agent_route_datasets(),
    )


@router.get(
    "/evaluation/agent-workflow/datasets",
    response_model=AgentWorkflowEvalDatasetListResponse,
)
def get_agent_workflow_datasets() -> AgentWorkflowEvalDatasetListResponse:
    return AgentWorkflowEvalDatasetListResponse(
        datasets=agent_workflow_eval_service.list_agent_workflow_datasets(),
    )


@router.get(
    "/evaluation/tool-execution/datasets",
    response_model=ToolExecutionEvalDatasetListResponse,
)
def get_tool_execution_datasets() -> ToolExecutionEvalDatasetListResponse:
    return ToolExecutionEvalDatasetListResponse(
        datasets=tool_execution_eval_service.list_tool_execution_datasets(),
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


@router.post("/evaluation/agent-route", response_model=AgentRouteEvalResponse)
def evaluate_agent_route(request: AgentRouteEvalRequest) -> AgentRouteEvalResponse:
    try:
        report = agent_route_eval_service.evaluate_named_agent_route_dataset(
            dataset_name=request.dataset_name,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation dataset not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return AgentRouteEvalResponse(
        dataset_name=request.dataset_name,
        report=report,
    )


@router.post("/evaluation/agent-workflow", response_model=AgentWorkflowEvalResponse)
def evaluate_agent_workflow(request: AgentWorkflowEvalRequest) -> AgentWorkflowEvalResponse:
    try:
        report = agent_workflow_eval_service.evaluate_named_agent_workflow_dataset(
            dataset_name=request.dataset_name,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation dataset not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return AgentWorkflowEvalResponse(
        dataset_name=request.dataset_name,
        report=report,
    )


@router.post("/evaluation/tool-execution", response_model=ToolExecutionEvalResponse)
def evaluate_tool_execution(request: ToolExecutionEvalRequest) -> ToolExecutionEvalResponse:
    try:
        report = tool_execution_eval_service.evaluate_named_tool_execution_dataset(
            dataset_name=request.dataset_name,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation dataset not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ToolExecutionEvalResponse(
        dataset_name=request.dataset_name,
        report=report,
    )
