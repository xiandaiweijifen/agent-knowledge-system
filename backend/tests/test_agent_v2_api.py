from fastapi.testclient import TestClient

from app.main import app


def test_query_agent_v2_endpoint_returns_agent_workflow_response(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.query.orchestrate_agent_v2_request",
        lambda question, filename=None, top_k=3, checkpointer=None: type(
            "Response",
            (),
            {
                "model_dump": lambda self=None: None,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.api.routes.query.orchestrate_agent_v2_request",
        lambda question, filename=None, top_k=3, checkpointer=None: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowResponse", "RouteDecision"]
        ).AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            route=__import__(
                "app.schemas.query", fromlist=["RouteDecision"]
            ).RouteDecision(
                route_type="knowledge_retrieval",
                route_reason="Knowledge question.",
                filename=filename,
            ),
            answer="Answer will be generated here.",
            answer_source="stub",
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/query/agent-v2",
        json={
            "question": "What is LangGraph?",
            "filename": "doc.txt",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "What is LangGraph?"
    assert payload["workflow_status"] == "completed"
    assert payload["route"]["route_type"] == "knowledge_retrieval"


def test_query_agent_v2_endpoint_returns_400_for_invalid_question():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent-v2",
        json={
            "question": "   ",
            "filename": "doc.txt",
            "top_k": 3,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "question_must_not_be_empty"


def test_resume_agent_v2_endpoint_returns_persisted_response(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.query.resume_agent_v2_request",
        lambda run_id, checkpointer=None: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowResponse", "RouteDecision"]
        ).AgentWorkflowResponse(
            run_id=run_id,
            question="What is LangGraph?",
            workflow_status="completed",
            route=__import__(
                "app.schemas.query", fromlist=["RouteDecision"]
            ).RouteDecision(
                route_type="knowledge_retrieval",
                route_reason="Knowledge question.",
                filename="doc.txt",
            ),
            answer="Resumed answer",
            answer_source="fallback",
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/query/agent-v2/resume",
        json={
            "run_id": "run-123",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-123"
    assert payload["answer"] == "Resumed answer"


def test_list_agent_v2_runs_endpoint_returns_runs(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.query.list_agent_v2_runs",
        lambda limit=20: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowRunListResponse", "AgentWorkflowRunSummary"]
        ).AgentWorkflowRunListResponse(
            runs=[
                __import__(
                    "app.schemas.query", fromlist=["AgentWorkflowRunSummary"]
                ).AgentWorkflowRunSummary(
                    run_id="run-123",
                    question="What is LangGraph?",
                    workflow_status="completed",
                    route_type="knowledge_retrieval",
                    route_reason="Knowledge question.",
                )
            ]
        ),
    )
    client = TestClient(app)
    response = client.get("/api/query/agent-v2/runs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["run_id"] == "run-123"


def test_get_agent_v2_run_endpoint_returns_single_run(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.query.get_persisted_agent_v2_run",
        lambda run_id: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowResponse", "RouteDecision"]
        ).AgentWorkflowResponse(
            run_id=run_id,
            question="What is LangGraph?",
            workflow_status="completed",
            route=__import__(
                "app.schemas.query", fromlist=["RouteDecision"]
            ).RouteDecision(
                route_type="knowledge_retrieval",
                route_reason="Knowledge question.",
                filename="doc.txt",
            ),
            answer="Stored answer",
            answer_source="fallback",
        ),
    )
    client = TestClient(app)
    response = client.get("/api/query/agent-v2/runs/run-123")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-123"
