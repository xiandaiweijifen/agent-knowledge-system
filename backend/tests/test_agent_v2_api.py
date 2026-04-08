from fastapi.testclient import TestClient

from app.main import app


def test_query_agent_v2_endpoint_returns_agent_workflow_response(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.query.orchestrate_agent_v2_request",
        lambda question, filename=None, top_k=3, checkpointer=None, debug_fault_injection=None: type(
            "Response",
            (),
            {
                "model_dump": lambda self=None: None,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.api.routes.query.orchestrate_agent_v2_request",
        lambda question, filename=None, top_k=3, checkpointer=None, debug_fault_injection=None: __import__(
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
        lambda run_id, clarification_context=None, checkpointer=None: __import__(
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


def test_query_agent_v2_stream_endpoint_returns_sse_events(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.query.stream_agent_v2_request",
        lambda question, filename=None, top_k=3, checkpointer=None, debug_fault_injection=None: iter(
            [
                {
                    "event_type": "status",
                    "stage": "start",
                    "status": "in_progress",
                    "detail": "Agent workflow started.",
                    "timestamp": "2026-04-08T00:00:00+00:00",
                    "payload": {"question": question},
                },
                {
                    "event_type": "result",
                    "response": {
                        "question": question,
                        "workflow_status": "completed",
                    },
                },
            ]
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/query/agent-v2/stream",
        json={
            "question": "What is LangGraph?",
            "filename": "doc.txt",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in response.text
    assert "event: result" in response.text


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


def test_query_agent_endpoint_uses_agent_v2_when_configured(monkeypatch):
    monkeypatch.setenv("ALLOW_AGENT_V2_DEFAULT_RUNTIME_IN_TESTS", "1")
    monkeypatch.setattr("app.api.routes.query.settings.agent_default_runtime", "v2")
    monkeypatch.setattr(
        "app.api.routes.query.orchestrate_agent_v2_request",
        lambda question, filename=None, top_k=3, checkpointer=None, debug_fault_injection=None: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowResponse", "RouteDecision"]
        ).AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            route=__import__(
                "app.schemas.query", fromlist=["RouteDecision"]
            ).RouteDecision(
                route_type="tool_execution",
                route_reason="V2 route.",
                filename=filename,
            ),
            answer="V2 answer",
            answer_source="tool_result",
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket",
            "filename": None,
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "V2 answer"
    assert payload["route"]["route_reason"] == "V2 route."


def test_list_agent_runs_endpoint_uses_agent_v2_when_configured(monkeypatch):
    monkeypatch.setenv("ALLOW_AGENT_V2_DEFAULT_RUNTIME_IN_TESTS", "1")
    monkeypatch.setattr("app.api.routes.query.settings.agent_default_runtime", "v2")
    monkeypatch.setattr(
        "app.api.routes.query.list_agent_v2_runs",
        lambda limit=20: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowRunListResponse", "AgentWorkflowRunSummary"]
        ).AgentWorkflowRunListResponse(
            runs=[
                __import__(
                    "app.schemas.query", fromlist=["AgentWorkflowRunSummary"]
                ).AgentWorkflowRunSummary(
                    run_id="v2-run-123",
                    question="Create a ticket",
                    workflow_status="completed",
                    route_type="tool_execution",
                    route_reason="V2 route.",
                )
            ]
        ),
    )
    client = TestClient(app)
    response = client.get("/api/query/agent/runs?limit=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["run_id"] == "v2-run-123"


def test_get_agent_run_endpoint_uses_agent_v2_when_configured(monkeypatch):
    monkeypatch.setenv("ALLOW_AGENT_V2_DEFAULT_RUNTIME_IN_TESTS", "1")
    monkeypatch.setattr("app.api.routes.query.settings.agent_default_runtime", "v2")
    monkeypatch.setattr(
        "app.api.routes.query.get_persisted_agent_v2_run",
        lambda run_id: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowResponse", "RouteDecision"]
        ).AgentWorkflowResponse(
            run_id=run_id,
            question="Create a ticket",
            workflow_status="completed",
            route=__import__(
                "app.schemas.query", fromlist=["RouteDecision"]
            ).RouteDecision(
                route_type="tool_execution",
                route_reason="V2 route.",
                filename=None,
            ),
            answer="Stored v2 answer",
            answer_source="tool_result",
        ),
    )
    client = TestClient(app)
    response = client.get("/api/query/agent/runs/v2-run-123")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "v2-run-123"
    assert payload["answer"] == "Stored v2 answer"


def test_recover_agent_endpoint_uses_agent_v2_resume_for_clarification_when_configured(monkeypatch):
    monkeypatch.setenv("ALLOW_AGENT_V2_DEFAULT_RUNTIME_IN_TESTS", "1")
    monkeypatch.setattr("app.api.routes.query.settings.agent_default_runtime", "v2")
    monkeypatch.setattr(
        "app.api.routes.query.recover_agent_v2_request",
        lambda run_id, recovery_action=None, clarification_context=None, checkpointer=None, debug_fault_injection=None: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowResponse", "RouteDecision"]
        ).AgentWorkflowResponse(
            run_id=run_id,
            question="Fix it (environment: production)",
            workflow_status="completed",
            route=__import__(
                "app.schemas.query", fromlist=["RouteDecision"]
            ).RouteDecision(
                route_type="tool_execution",
                route_reason="Clarification applied.",
                filename=None,
            ),
            answer="Recovered via v2 resume",
            answer_source="tool_result",
            recovered_via_action="resume_with_clarification",
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/query/agent/recover",
        json={
            "run_id": "run-clarify-123",
            "recovery_action": "resume_with_clarification",
            "clarification_context": {
                "environment": "production",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-clarify-123"
    assert payload["answer"] == "Recovered via v2 resume"


def test_recover_agent_endpoint_rejects_unsupported_v2_recovery_action(monkeypatch):
    monkeypatch.setenv("ALLOW_AGENT_V2_DEFAULT_RUNTIME_IN_TESTS", "1")
    monkeypatch.setattr("app.api.routes.query.settings.agent_default_runtime", "v2")
    monkeypatch.setattr(
        "app.api.routes.query.recover_agent_v2_request",
        lambda run_id, recovery_action=None, clarification_context=None, checkpointer=None, debug_fault_injection=None: (_ for _ in ()).throw(
            ValueError("recovery_action_not_supported_for_agent_v2")
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/query/agent/recover",
        json={
            "run_id": "run-failed-123",
            "recovery_action": "manual_retrigger",
            "clarification_context": {},
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "recovery_action_not_supported_for_agent_v2"


def test_recover_agent_endpoint_uses_agent_v2_manual_retrigger_when_configured(monkeypatch):
    monkeypatch.setenv("ALLOW_AGENT_V2_DEFAULT_RUNTIME_IN_TESTS", "1")
    monkeypatch.setattr("app.api.routes.query.settings.agent_default_runtime", "v2")
    monkeypatch.setattr(
        "app.api.routes.query.recover_agent_v2_request",
        lambda run_id, recovery_action=None, clarification_context=None, checkpointer=None, debug_fault_injection=None: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowResponse", "RouteDecision"]
        ).AgentWorkflowResponse(
            run_id="rerun-123",
            root_run_id=run_id,
            recovery_depth=1,
            question="Create a ticket for payment-service outage",
            source_run_id=run_id,
            recovered_via_action="manual_retrigger",
            resume_source_type="run_id",
            resume_strategy="manual_retrigger_recovery",
            workflow_status="completed",
            route=__import__(
                "app.schemas.query", fromlist=["RouteDecision"]
            ).RouteDecision(
                route_type="tool_execution",
                route_reason="Retried from failure.",
                filename=None,
            ),
            answer="Recovered via manual retrigger",
            answer_source="tool_result",
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/query/agent/recover",
        json={
            "run_id": "run-failed-123",
            "recovery_action": "manual_retrigger",
            "clarification_context": {},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "rerun-123"
    assert payload["recovered_via_action"] == "manual_retrigger"


def test_recover_agent_endpoint_uses_agent_v2_failed_step_resume_when_configured(monkeypatch):
    monkeypatch.setenv("ALLOW_AGENT_V2_DEFAULT_RUNTIME_IN_TESTS", "1")
    monkeypatch.setattr("app.api.routes.query.settings.agent_default_runtime", "v2")
    monkeypatch.setattr(
        "app.api.routes.query.recover_agent_v2_request",
        lambda run_id, recovery_action=None, clarification_context=None, checkpointer=None, debug_fault_injection=None: __import__(
            "app.schemas.query", fromlist=["AgentWorkflowResponse", "RouteDecision"]
        ).AgentWorkflowResponse(
            run_id="rerun-step-123",
            root_run_id=run_id,
            recovery_depth=1,
            question="Create a ticket for payment-service outage",
            source_run_id=run_id,
            recovered_via_action="resume_from_failed_step",
            resume_source_type="run_id",
            resume_strategy="failed_step_resume",
            resumed_from_step_index=1,
            retried_step_indices=[1],
            workflow_status="completed",
            route=__import__(
                "app.schemas.query", fromlist=["RouteDecision"]
            ).RouteDecision(
                route_type="tool_execution",
                route_reason="Retried from failed step.",
                filename=None,
            ),
            answer="Recovered via failed-step resume",
            answer_source="tool_result",
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/query/agent/recover",
        json={
            "run_id": "run-failed-456",
            "recovery_action": "resume_from_failed_step",
            "clarification_context": {},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "rerun-step-123"
    assert payload["recovered_via_action"] == "resume_from_failed_step"
    assert payload["resume_strategy"] == "failed_step_resume"
