from pathlib import Path

from app.schemas.query import AgentWorkflowResponse, RouteDecision
from app.services.agent_v2 import run_store

TMP_DIR = Path(__file__).resolve().parent / "_tmp"


def test_agent_v2_run_store_persists_and_loads_runs(monkeypatch):
    monkeypatch.setattr(
        run_store,
        "AGENT_V2_RUN_STORE_PATH",
        TMP_DIR / "workflow_runs_v2_store_test_load.json",
    )

    response = AgentWorkflowResponse(
        run_id="run-123",
        question="What is LangGraph?",
        workflow_status="completed",
        route=RouteDecision(
            route_type="knowledge_retrieval",
            route_reason="Knowledge question.",
            filename="doc.txt",
        ),
        answer="Stored answer",
        answer_source="fallback",
        last_updated_at="2026-04-07T00:00:00+00:00",
    )

    run_store.persist_agent_v2_run(response)

    persisted = run_store.get_persisted_agent_v2_run("run-123")
    assert persisted.run_id == "run-123"
    assert persisted.answer == "Stored answer"


def test_agent_v2_run_store_lists_runs_in_latest_first_order(monkeypatch):
    monkeypatch.setattr(
        run_store,
        "AGENT_V2_RUN_STORE_PATH",
        TMP_DIR / "workflow_runs_v2_store_test_list.json",
    )

    run_store.persist_agent_v2_run(
        AgentWorkflowResponse(
            run_id="run-older",
            question="Older",
            workflow_status="completed",
            route=RouteDecision(
                route_type="knowledge_retrieval",
                route_reason="Older",
                filename=None,
            ),
            last_updated_at="2026-04-07T00:00:00+00:00",
        )
    )
    run_store.persist_agent_v2_run(
        AgentWorkflowResponse(
            run_id="run-newer",
            question="Newer",
            workflow_status="completed",
            route=RouteDecision(
                route_type="knowledge_retrieval",
                route_reason="Newer",
                filename=None,
            ),
            last_updated_at="2026-04-07T00:00:01+00:00",
        )
    )

    runs = run_store.list_persisted_agent_v2_runs(limit=10)
    assert [run.run_id for run in runs.runs] == ["run-newer", "run-older"]
