from datetime import datetime, timezone

from app.schemas.evaluation_api import (
    EvaluationExportBundleMode,
    EvaluationExportBundleReports,
    EvaluationExportBundleResponse,
)
from app.services.evaluation import metrics_summary_service, overview_service, report_store_service
from app.services.evaluation.metrics_summary_service import (
    SHOWCASE_RETRIEVAL_DATASET,
    SHOWCASE_RETRIEVAL_TOP_K,
    SHOWCASE_ROUTE_DATASET,
    SHOWCASE_TOOL_EXECUTION_DATASET,
    SHOWCASE_WORKFLOW_DATASET,
)


def get_evaluation_export_bundle(refresh: bool = False) -> EvaluationExportBundleResponse:
    overview = overview_service.get_evaluation_overview(refresh=refresh)
    metrics_summary = metrics_summary_service.get_metrics_summary(refresh=refresh)

    return EvaluationExportBundleResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        overview=overview,
        metrics_summary=metrics_summary,
        reports=EvaluationExportBundleReports(
            retrieval=EvaluationExportBundleMode(
                dataset_name=SHOWCASE_RETRIEVAL_DATASET,
                top_k=SHOWCASE_RETRIEVAL_TOP_K,
                latest_report=report_store_service.load_latest_retrieval_report(
                    dataset_name=SHOWCASE_RETRIEVAL_DATASET,
                    top_k=SHOWCASE_RETRIEVAL_TOP_K,
                ),
                history=report_store_service.list_retrieval_report_history(
                    dataset_name=SHOWCASE_RETRIEVAL_DATASET,
                    top_k=SHOWCASE_RETRIEVAL_TOP_K,
                ),
            ),
            agent_route=EvaluationExportBundleMode(
                dataset_name=SHOWCASE_ROUTE_DATASET,
                latest_report=report_store_service.load_latest_agent_route_report(
                    dataset_name=SHOWCASE_ROUTE_DATASET,
                ),
                history=report_store_service.list_agent_route_report_history(
                    dataset_name=SHOWCASE_ROUTE_DATASET,
                ),
            ),
            agent_workflow=EvaluationExportBundleMode(
                dataset_name=SHOWCASE_WORKFLOW_DATASET,
                latest_report=report_store_service.load_latest_agent_workflow_report(
                    dataset_name=SHOWCASE_WORKFLOW_DATASET,
                ),
                history=report_store_service.list_agent_workflow_report_history(
                    dataset_name=SHOWCASE_WORKFLOW_DATASET,
                ),
            ),
            tool_execution=EvaluationExportBundleMode(
                dataset_name=SHOWCASE_TOOL_EXECUTION_DATASET,
                latest_report=report_store_service.load_latest_tool_execution_report(
                    dataset_name=SHOWCASE_TOOL_EXECUTION_DATASET,
                ),
                history=report_store_service.list_tool_execution_report_history(
                    dataset_name=SHOWCASE_TOOL_EXECUTION_DATASET,
                ),
            ),
        ),
    )
