from app.services.evaluation import overview_service


def test_get_evaluation_overview_reads_cached_payload(workspace_tmp_path, monkeypatch):
    cache_path = workspace_tmp_path / "evaluation_overview_cache.json"
    cache_path.write_text(
        """
{
  "generated_at": "2026-03-17T00:00:00+00:00",
  "cache_status": "fresh",
  "retrieval": {
    "dataset_count": 2,
    "total_cases": 14,
    "mean_hit_rate_at_k": 1.0,
    "mean_reciprocal_rank": 1.0,
    "best_dataset_name": "rag_overview_retrieval_eval.json",
    "best_hit_rate_at_k": 1.0
  },
  "workflow": {
    "total_run_count": 20,
    "completed_run_count": 10,
    "clarification_required_run_count": 5,
    "failed_run_count": 5,
    "completion_rate": 0.5,
    "clarification_rate": 0.25,
    "failed_rate": 0.25
  },
  "recovery": {
    "recovered_run_count": 4,
    "recovered_completed_run_count": 3,
    "recovery_success_rate": 0.75,
    "average_recovery_depth": 1.25,
    "resume_from_failed_step_count": 2,
    "manual_retrigger_count": 1,
    "clarification_recovery_count": 1
  }
}
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(overview_service, "OVERVIEW_CACHE_PATH", cache_path)

    payload = overview_service.get_evaluation_overview()

    assert payload.cache_status == "cached"
    assert payload.retrieval.dataset_count == 2
    assert payload.workflow.total_run_count == 20


def test_get_evaluation_overview_refresh_recomputes_and_persists(workspace_tmp_path, monkeypatch):
    cache_path = workspace_tmp_path / "evaluation_overview_cache.json"
    monkeypatch.setattr(overview_service, "OVERVIEW_CACHE_PATH", cache_path)

    computed = overview_service.EvaluationOverviewResponse(
        generated_at="2026-03-17T00:00:00+00:00",
        cache_status="fresh",
        retrieval=overview_service.EvaluationOverviewRetrievalSummary(
            dataset_count=1,
            total_cases=6,
            mean_hit_rate_at_k=0.9,
            mean_reciprocal_rank=0.8,
            best_dataset_name="rag_overview_retrieval_eval.json",
            best_hit_rate_at_k=0.9,
        ),
        workflow=overview_service.EvaluationOverviewWorkflowSummary(
            total_run_count=10,
            completed_run_count=6,
            clarification_required_run_count=2,
            failed_run_count=2,
            completion_rate=0.6,
            clarification_rate=0.2,
            failed_rate=0.2,
        ),
        recovery=overview_service.EvaluationOverviewRecoverySummary(
            recovered_run_count=3,
            recovered_completed_run_count=3,
            recovery_success_rate=1.0,
            average_recovery_depth=1.0,
            resume_from_failed_step_count=2,
            manual_retrigger_count=1,
            clarification_recovery_count=0,
        ),
    )

    monkeypatch.setattr(overview_service, "_build_evaluation_overview", lambda top_k=3: computed)

    payload = overview_service.get_evaluation_overview(refresh=True)

    assert payload.cache_status == "fresh"
    assert cache_path.exists()
    assert "rag_overview_retrieval_eval.json" in cache_path.read_text(encoding="utf-8")
