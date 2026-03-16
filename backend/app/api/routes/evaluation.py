from fastapi import APIRouter, HTTPException

from app.schemas.evaluation_api import (
    AgentRouteEvalDatasetListResponse,
    AgentRouteEvalRequest,
    AgentRouteEvalResponse,
    EvaluationExportBundleResponse,
    EvaluationReportHistoryResponse,
    EvaluationMetricsSummaryResponse,
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
    export_bundle_service,
    tool_execution_eval_service,
    agent_workflow_eval_service,
    metrics_summary_service,
    overview_service,
    report_store_service,
    retrieval_eval_service,
)

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation/overview", response_model=EvaluationOverviewResponse)
def get_evaluation_overview(refresh: bool = False) -> EvaluationOverviewResponse:
    return overview_service.get_evaluation_overview(refresh=refresh)


@router.get("/evaluation/metrics-summary", response_model=EvaluationMetricsSummaryResponse)
def get_evaluation_metrics_summary(refresh: bool = False) -> EvaluationMetricsSummaryResponse:
    return metrics_summary_service.get_metrics_summary(refresh=refresh)


@router.get("/evaluation/export-bundle", response_model=EvaluationExportBundleResponse)
def get_evaluation_export_bundle(refresh: bool = False) -> EvaluationExportBundleResponse:
    return export_bundle_service.get_evaluation_export_bundle(refresh=refresh)


@router.get("/evaluation/retrieval/datasets", response_model=RetrievalEvalDatasetListResponse)
def get_retrieval_datasets() -> RetrievalEvalDatasetListResponse:
    return RetrievalEvalDatasetListResponse(
        datasets=retrieval_eval_service.list_retrieval_datasets(),
    )


@router.get("/evaluation/retrieval/latest", response_model=RetrievalEvalResponse)
def get_latest_retrieval_report(dataset_name: str, top_k: int = 3) -> RetrievalEvalResponse:
    payload = report_store_service.load_latest_retrieval_report(
        dataset_name=dataset_name,
        top_k=top_k,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="evaluation_report_not_found")

    return RetrievalEvalResponse.model_validate(payload)


@router.get("/evaluation/retrieval/history", response_model=EvaluationReportHistoryResponse)
def get_retrieval_report_history(
    dataset_name: str,
    top_k: int = 3,
    limit: int = 5,
) -> EvaluationReportHistoryResponse:
    return EvaluationReportHistoryResponse(
        entries=report_store_service.list_retrieval_report_history(
            dataset_name=dataset_name,
            top_k=top_k,
            limit=limit,
        ),
    )


@router.get("/evaluation/agent-route/datasets", response_model=AgentRouteEvalDatasetListResponse)
def get_agent_route_datasets() -> AgentRouteEvalDatasetListResponse:
    return AgentRouteEvalDatasetListResponse(
        datasets=agent_route_eval_service.list_agent_route_datasets(),
    )


@router.get("/evaluation/agent-route/latest", response_model=AgentRouteEvalResponse)
def get_latest_agent_route_report(dataset_name: str) -> AgentRouteEvalResponse:
    payload = report_store_service.load_latest_agent_route_report(dataset_name=dataset_name)
    if payload is None:
        raise HTTPException(status_code=404, detail="evaluation_report_not_found")

    return AgentRouteEvalResponse.model_validate(payload)


@router.get("/evaluation/agent-route/history", response_model=EvaluationReportHistoryResponse)
def get_agent_route_report_history(dataset_name: str, limit: int = 5) -> EvaluationReportHistoryResponse:
    return EvaluationReportHistoryResponse(
        entries=report_store_service.list_agent_route_report_history(
            dataset_name=dataset_name,
            limit=limit,
        ),
    )


@router.get(
    "/evaluation/agent-workflow/datasets",
    response_model=AgentWorkflowEvalDatasetListResponse,
)
def get_agent_workflow_datasets() -> AgentWorkflowEvalDatasetListResponse:
    return AgentWorkflowEvalDatasetListResponse(
        datasets=agent_workflow_eval_service.list_agent_workflow_datasets(),
    )


@router.get("/evaluation/agent-workflow/latest", response_model=AgentWorkflowEvalResponse)
def get_latest_agent_workflow_report(dataset_name: str) -> AgentWorkflowEvalResponse:
    payload = report_store_service.load_latest_agent_workflow_report(dataset_name=dataset_name)
    if payload is None:
        raise HTTPException(status_code=404, detail="evaluation_report_not_found")

    return AgentWorkflowEvalResponse.model_validate(payload)


@router.get("/evaluation/agent-workflow/history", response_model=EvaluationReportHistoryResponse)
def get_agent_workflow_report_history(dataset_name: str, limit: int = 5) -> EvaluationReportHistoryResponse:
    return EvaluationReportHistoryResponse(
        entries=report_store_service.list_agent_workflow_report_history(
            dataset_name=dataset_name,
            limit=limit,
        ),
    )


@router.get(
    "/evaluation/tool-execution/datasets",
    response_model=ToolExecutionEvalDatasetListResponse,
)
def get_tool_execution_datasets() -> ToolExecutionEvalDatasetListResponse:
    return ToolExecutionEvalDatasetListResponse(
        datasets=tool_execution_eval_service.list_tool_execution_datasets(),
    )


@router.get("/evaluation/tool-execution/latest", response_model=ToolExecutionEvalResponse)
def get_latest_tool_execution_report(dataset_name: str) -> ToolExecutionEvalResponse:
    payload = report_store_service.load_latest_tool_execution_report(dataset_name=dataset_name)
    if payload is None:
        raise HTTPException(status_code=404, detail="evaluation_report_not_found")

    return ToolExecutionEvalResponse.model_validate(payload)


@router.get("/evaluation/tool-execution/history", response_model=EvaluationReportHistoryResponse)
def get_tool_execution_report_history(dataset_name: str, limit: int = 5) -> EvaluationReportHistoryResponse:
    return EvaluationReportHistoryResponse(
        entries=report_store_service.list_tool_execution_report_history(
            dataset_name=dataset_name,
            limit=limit,
        ),
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

    persisted = report_store_service.persist_retrieval_report(
        dataset_name=request.dataset_name,
        top_k=request.top_k,
        report=report,
    )

    return RetrievalEvalResponse(
        dataset_name=request.dataset_name,
        report=report,
        saved_at=persisted["saved_at"],
        report_source=persisted["report_source"],
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

    persisted = report_store_service.persist_agent_route_report(
        dataset_name=request.dataset_name,
        report=report,
    )

    return AgentRouteEvalResponse(
        dataset_name=request.dataset_name,
        report=report,
        saved_at=persisted["saved_at"],
        report_source=persisted["report_source"],
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

    persisted = report_store_service.persist_agent_workflow_report(
        dataset_name=request.dataset_name,
        report=report,
    )

    return AgentWorkflowEvalResponse(
        dataset_name=request.dataset_name,
        report=report,
        saved_at=persisted["saved_at"],
        report_source=persisted["report_source"],
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

    persisted = report_store_service.persist_tool_execution_report(
        dataset_name=request.dataset_name,
        report=report,
    )

    return ToolExecutionEvalResponse(
        dataset_name=request.dataset_name,
        report=report,
        saved_at=persisted["saved_at"],
        report_source=persisted["report_source"],
    )
