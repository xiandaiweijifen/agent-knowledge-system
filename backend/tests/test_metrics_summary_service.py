from app.services.evaluation import metrics_summary_service


def test_get_metrics_summary_reads_cached_payload(workspace_tmp_path, monkeypatch):
    cache_path = workspace_tmp_path / "evaluation_metrics_summary.json"
    cache_path.write_text(
        """
{
  "generated_at": "2026-03-17T03:00:00+00:00",
  "cache_status": "fresh",
  "highlights": [
    {
      "label": "Workflow Completion",
      "value": "63.7%",
      "detail": "107/168 runs completed."
    }
  ],
  "sections": [
    {
      "title": "Showcase Retrieval Benchmark",
      "dataset_name": "agent_workflow_retrieval_eval.json",
      "metric_name": "hit_rate_at_k",
      "metric_value": 1.0,
      "formatted_value": "1.000",
      "detail": "MRR 0.917 at top-3."
    }
  ]
}
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(metrics_summary_service, "METRICS_SUMMARY_CACHE_PATH", cache_path)

    payload = metrics_summary_service.get_metrics_summary()

    assert payload.cache_status == "cached"
    assert payload.highlights[0].label == "Workflow Completion"


def test_get_metrics_summary_refresh_recomputes_and_persists(workspace_tmp_path, monkeypatch):
    cache_path = workspace_tmp_path / "evaluation_metrics_summary.json"
    monkeypatch.setattr(metrics_summary_service, "METRICS_SUMMARY_CACHE_PATH", cache_path)

    computed = metrics_summary_service.EvaluationMetricsSummaryResponse(
        generated_at="2026-03-17T03:00:00+00:00",
        cache_status="fresh",
        highlights=[
            metrics_summary_service.EvaluationMetricHighlight(
                label="Workflow Completion",
                value="63.7%",
                detail="107/168 runs completed.",
            )
        ],
        sections=[
            metrics_summary_service.EvaluationMetricsSummarySection(
                title="Showcase Retrieval Benchmark",
                dataset_name="agent_workflow_retrieval_eval.json",
                metric_name="hit_rate_at_k",
                metric_value=1.0,
                formatted_value="1.000",
                detail="MRR 0.917 at top-3.",
            )
        ],
    )

    monkeypatch.setattr(metrics_summary_service, "_build_metrics_summary", lambda: computed)

    payload = metrics_summary_service.get_metrics_summary(refresh=True)

    assert payload.cache_status == "fresh"
    assert cache_path.exists()
    assert "Workflow Completion" in cache_path.read_text(encoding="utf-8")
