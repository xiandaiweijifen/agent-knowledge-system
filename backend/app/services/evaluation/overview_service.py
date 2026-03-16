import json
from datetime import datetime, timezone

from app.core.config import DATA_ROOT
from app.schemas.evaluation_api import (
    EvaluationOverviewRecoverySummary,
    EvaluationOverviewResponse,
    EvaluationOverviewRetrievalSummary,
    EvaluationOverviewWorkflowSummary,
)
from app.services.agent.orchestrator_service import get_all_persisted_workflow_runs
from app.services.evaluation import retrieval_eval_service

OVERVIEW_CACHE_PATH = DATA_ROOT / "tool_state" / "evaluation_overview_cache.json"


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _build_evaluation_overview(top_k: int = 3) -> EvaluationOverviewResponse:
    retrieval_datasets = retrieval_eval_service.list_retrieval_datasets()
    retrieval_reports = [
        retrieval_eval_service.evaluate_named_retrieval_dataset(dataset.dataset_name, top_k)
        for dataset in retrieval_datasets
    ]

    total_retrieval_cases = sum(report.summary.total_cases for report in retrieval_reports)
    mean_hit_rate = (
        sum(report.summary.hit_rate_at_k for report in retrieval_reports) / len(retrieval_reports)
        if retrieval_reports
        else 0.0
    )
    mean_mrr = (
        sum(report.summary.mean_reciprocal_rank for report in retrieval_reports) / len(retrieval_reports)
        if retrieval_reports
        else 0.0
    )
    best_dataset = max(
        zip(retrieval_datasets, retrieval_reports),
        key=lambda item: item[1].summary.hit_rate_at_k,
        default=None,
    )

    persisted_runs = get_all_persisted_workflow_runs()
    total_run_count = len(persisted_runs)
    completed_run_count = sum(1 for run in persisted_runs if run.workflow_status == "completed")
    clarification_required_run_count = sum(
        1 for run in persisted_runs if run.workflow_status == "clarification_required"
    )
    failed_run_count = sum(1 for run in persisted_runs if run.workflow_status == "failed")

    recovered_runs = [run for run in persisted_runs if run.source_run_id]
    recovered_completed_runs = [run for run in recovered_runs if run.workflow_status == "completed"]

    return EvaluationOverviewResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        cache_status="fresh",
        retrieval=EvaluationOverviewRetrievalSummary(
            dataset_count=len(retrieval_datasets),
            total_cases=total_retrieval_cases,
            mean_hit_rate_at_k=mean_hit_rate,
            mean_reciprocal_rank=mean_mrr,
            best_dataset_name=best_dataset[0].dataset_name if best_dataset else None,
            best_hit_rate_at_k=best_dataset[1].summary.hit_rate_at_k if best_dataset else 0.0,
        ),
        workflow=EvaluationOverviewWorkflowSummary(
            total_run_count=total_run_count,
            completed_run_count=completed_run_count,
            clarification_required_run_count=clarification_required_run_count,
            failed_run_count=failed_run_count,
            completion_rate=_safe_rate(completed_run_count, total_run_count),
            clarification_rate=_safe_rate(clarification_required_run_count, total_run_count),
            failed_rate=_safe_rate(failed_run_count, total_run_count),
        ),
        recovery=EvaluationOverviewRecoverySummary(
            recovered_run_count=len(recovered_runs),
            recovered_completed_run_count=len(recovered_completed_runs),
            recovery_success_rate=_safe_rate(len(recovered_completed_runs), len(recovered_runs)),
            average_recovery_depth=(
                sum(run.recovery_depth for run in recovered_runs) / len(recovered_runs)
                if recovered_runs
                else 0.0
            ),
            resume_from_failed_step_count=sum(
                1 for run in recovered_runs if run.recovered_via_action == "resume_from_failed_step"
            ),
            manual_retrigger_count=sum(
                1 for run in recovered_runs if run.recovered_via_action == "manual_retrigger"
            ),
            clarification_recovery_count=sum(
                1 for run in recovered_runs if run.recovered_via_action == "resume_with_clarification"
            ),
        ),
    )


def _load_cached_evaluation_overview() -> EvaluationOverviewResponse | None:
    if not OVERVIEW_CACHE_PATH.exists():
        return None

    payload = json.loads(OVERVIEW_CACHE_PATH.read_text(encoding="utf-8"))
    cached = EvaluationOverviewResponse.model_validate(payload)
    cached.cache_status = "cached"
    return cached


def _persist_evaluation_overview(overview: EvaluationOverviewResponse) -> None:
    OVERVIEW_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERVIEW_CACHE_PATH.write_text(
        overview.model_dump_json(indent=2),
        encoding="utf-8",
    )


def get_evaluation_overview(top_k: int = 3, refresh: bool = False) -> EvaluationOverviewResponse:
    if not refresh:
        cached = _load_cached_evaluation_overview()
        if cached is not None:
            return cached

    overview = _build_evaluation_overview(top_k=top_k)
    _persist_evaluation_overview(overview)
    return overview
