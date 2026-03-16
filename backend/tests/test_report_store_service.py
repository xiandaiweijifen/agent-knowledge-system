from app.services.evaluation import report_store_service


def test_persist_and_load_latest_retrieval_report(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(report_store_service, "REPORT_STORE_DIR", workspace_tmp_path)

    persisted = report_store_service.persist_retrieval_report(
        dataset_name="rag_overview_retrieval_eval.json",
        top_k=3,
        report={
            "top_k": 3,
            "summary": {
                "total_cases": 2,
                "hit_rate_at_k": 1.0,
                "mean_reciprocal_rank": 1.0,
            },
            "cases": [],
        },
    )

    loaded = report_store_service.load_latest_retrieval_report(
        dataset_name="rag_overview_retrieval_eval.json",
        top_k=3,
    )

    assert persisted["report_source"] == "fresh"
    assert loaded is not None
    assert loaded["report_source"] == "saved"
    assert loaded["report"]["summary"]["total_cases"] == 2

    history = report_store_service.list_retrieval_report_history(
        dataset_name="rag_overview_retrieval_eval.json",
        top_k=3,
    )

    assert len(history) == 1
    assert history[0]["primary_metric_name"] == "hit_rate_at_k"


def test_persist_and_load_latest_agent_route_report(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(report_store_service, "REPORT_STORE_DIR", workspace_tmp_path)

    report_store_service.persist_agent_route_report(
        dataset_name="agent_route_eval.json",
        report={
            "summary": {
                "total_cases": 3,
                "route_accuracy": 1.0,
            },
            "cases": [],
        },
    )

    loaded = report_store_service.load_latest_agent_route_report("agent_route_eval.json")

    assert loaded is not None
    assert loaded["dataset_name"] == "agent_route_eval.json"
    assert loaded["report_source"] == "saved"
    assert report_store_service.list_agent_route_report_history("agent_route_eval.json")[0][
        "primary_metric_name"
    ] == "route_accuracy"


def test_persist_and_load_latest_agent_workflow_report(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(report_store_service, "REPORT_STORE_DIR", workspace_tmp_path)

    report_store_service.persist_agent_workflow_report(
        dataset_name="agent_workflow_eval.json",
        report={
            "summary": {
                "total_cases": 4,
                "workflow_accuracy": 0.75,
            },
            "cases": [],
        },
    )

    loaded = report_store_service.load_latest_agent_workflow_report("agent_workflow_eval.json")

    assert loaded is not None
    assert loaded["dataset_name"] == "agent_workflow_eval.json"
    assert loaded["report_source"] == "saved"
    assert report_store_service.list_agent_workflow_report_history("agent_workflow_eval.json")[0][
        "primary_metric_name"
    ] == "workflow_accuracy"


def test_persist_and_load_latest_tool_execution_report(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(report_store_service, "REPORT_STORE_DIR", workspace_tmp_path)

    report_store_service.persist_tool_execution_report(
        dataset_name="agent_tool_execution_eval.json",
        report={
            "summary": {
                "total_cases": 5,
                "tool_accuracy": 0.8,
            },
            "cases": [],
        },
    )

    loaded = report_store_service.load_latest_tool_execution_report("agent_tool_execution_eval.json")

    assert loaded is not None
    assert loaded["dataset_name"] == "agent_tool_execution_eval.json"
    assert loaded["report_source"] == "saved"
    assert report_store_service.list_tool_execution_report_history("agent_tool_execution_eval.json")[0][
        "primary_metric_name"
    ] == "tool_accuracy"
