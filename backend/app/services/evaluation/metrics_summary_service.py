import json
from datetime import datetime, timezone

from app.core.config import DATA_ROOT
from app.schemas.evaluation_api import (
    EvaluationMetricHighlight,
    EvaluationMetricsSummaryResponse,
    EvaluationMetricsSummarySection,
)
from app.services.evaluation import overview_service, report_store_service

METRICS_SUMMARY_CACHE_PATH = DATA_ROOT / "tool_state" / "evaluation_metrics_summary.json"

SHOWCASE_RETRIEVAL_DATASET = "agent_workflow_retrieval_eval.json"
SHOWCASE_RETRIEVAL_TOP_K = 3
SHOWCASE_ROUTE_DATASET = "agent_route_eval.json"
SHOWCASE_WORKFLOW_DATASET = "agent_workflow_eval.json"
SHOWCASE_TOOL_EXECUTION_DATASET = "agent_tool_execution_eval.json"


def _format_rate(value: float) -> str:
    return f"{value:.3f}"


def _format_percentage(value: float) -> str:
    return f"{value * 100:.1f}%"


def _build_metrics_summary() -> EvaluationMetricsSummaryResponse:
    overview = overview_service.get_evaluation_overview(refresh=False)
    retrieval_report = report_store_service.load_latest_retrieval_report(
        dataset_name=SHOWCASE_RETRIEVAL_DATASET,
        top_k=SHOWCASE_RETRIEVAL_TOP_K,
    )
    route_report = report_store_service.load_latest_agent_route_report(
        dataset_name=SHOWCASE_ROUTE_DATASET,
    )
    workflow_report = report_store_service.load_latest_agent_workflow_report(
        dataset_name=SHOWCASE_WORKFLOW_DATASET,
    )
    tool_execution_report = report_store_service.load_latest_tool_execution_report(
        dataset_name=SHOWCASE_TOOL_EXECUTION_DATASET,
    )

    sections: list[EvaluationMetricsSummarySection] = []

    if retrieval_report is not None:
        sections.append(
            EvaluationMetricsSummarySection(
                title="Showcase Retrieval",
                dataset_name=SHOWCASE_RETRIEVAL_DATASET,
                metric_name="hit_rate_at_k",
                metric_value=retrieval_report["report"]["summary"]["hit_rate_at_k"],
                formatted_value=_format_rate(retrieval_report["report"]["summary"]["hit_rate_at_k"]),
                detail=f"MRR {_format_rate(retrieval_report['report']['summary']['mean_reciprocal_rank'])} at top-{retrieval_report.get('top_k', SHOWCASE_RETRIEVAL_TOP_K)}.",
            )
        )

    if route_report is not None:
        sections.append(
            EvaluationMetricsSummarySection(
                title="Route Accuracy",
                dataset_name=SHOWCASE_ROUTE_DATASET,
                metric_name="route_accuracy",
                metric_value=route_report["report"]["summary"]["route_accuracy"],
                formatted_value=_format_rate(route_report["report"]["summary"]["route_accuracy"]),
                detail=f"{route_report['report']['summary']['total_cases']} evaluation cases.",
            )
        )

    if workflow_report is not None:
        sections.append(
            EvaluationMetricsSummarySection(
                title="Workflow Accuracy",
                dataset_name=SHOWCASE_WORKFLOW_DATASET,
                metric_name="workflow_accuracy",
                metric_value=workflow_report["report"]["summary"]["workflow_accuracy"],
                formatted_value=_format_rate(workflow_report["report"]["summary"]["workflow_accuracy"]),
                detail=f"{workflow_report['report']['summary']['total_cases']} workflow cases.",
            )
        )

    if tool_execution_report is not None:
        sections.append(
            EvaluationMetricsSummarySection(
                title="Tool Execution Accuracy",
                dataset_name=SHOWCASE_TOOL_EXECUTION_DATASET,
                metric_name="tool_accuracy",
                metric_value=tool_execution_report["report"]["summary"]["tool_accuracy"],
                formatted_value=_format_rate(tool_execution_report["report"]["summary"]["tool_accuracy"]),
                detail=f"{tool_execution_report['report']['summary']['total_cases']} tool execution cases.",
            )
        )

    highlights = [
        EvaluationMetricHighlight(
            label="Workflow Completion",
            value=_format_percentage(overview.workflow.completion_rate),
            detail=f"{overview.workflow.completed_run_count}/{overview.workflow.total_run_count} runs completed.",
        ),
        EvaluationMetricHighlight(
            label="Recovery Success",
            value=_format_percentage(overview.recovery.recovery_success_rate),
            detail=f"{overview.recovery.recovered_completed_run_count}/{overview.recovery.recovered_run_count} recovered runs completed.",
        ),
    ]

    return EvaluationMetricsSummaryResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        cache_status="fresh",
        highlights=highlights,
        sections=sections,
    )


def _load_cached_metrics_summary() -> EvaluationMetricsSummaryResponse | None:
    if not METRICS_SUMMARY_CACHE_PATH.exists():
        return None

    payload = json.loads(METRICS_SUMMARY_CACHE_PATH.read_text(encoding="utf-8"))
    cached = EvaluationMetricsSummaryResponse.model_validate(payload)
    cached.cache_status = "cached"
    return cached


def _persist_metrics_summary(summary: EvaluationMetricsSummaryResponse) -> None:
    METRICS_SUMMARY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_SUMMARY_CACHE_PATH.write_text(
        summary.model_dump_json(indent=2),
        encoding="utf-8",
    )


def get_metrics_summary(refresh: bool = False) -> EvaluationMetricsSummaryResponse:
    if not refresh:
        cached = _load_cached_metrics_summary()
        if cached is not None:
            return cached

    summary = _build_metrics_summary()
    _persist_metrics_summary(summary)
    return summary
