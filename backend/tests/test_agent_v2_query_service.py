from langgraph.types import Command

from app.services.agent_v2.query_service import (
    orchestrate_agent_v2_request,
    recover_agent_v2_request,
    stream_agent_v2_request,
)


def test_orchestrate_agent_v2_request_returns_retrieval_response(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "knowledge_retrieval",
                    "route_reason": "Knowledge question.",
                    "route_planning_mode": "llm_openai",
                    "workflow_status": "completed",
                    "answer": "retrieved answer",
                    "answer_source": "fallback",
                    "model": "gemini-2.5-flash",
                    "answered_at": "2026-04-07T00:00:00+00:00",
                    "answer_latency_ms": 123.0,
                    "chat_provider": "gemini",
                    "chat_model": "gemini-2.5-flash",
                    "retrieval_result": {
                        "filename": "doc.txt",
                        "embedding_provider": "gemini",
                        "embedding_model": "gemini-embedding-001",
                        "vector_dim": 3072,
                        "question": "What is LangGraph?",
                        "top_k": 3,
                        "retrieved_at": "2026-04-07T00:00:00+00:00",
                        "retrieval_latency_ms": 50.0,
                        "query_embedding_provider": "gemini",
                        "query_embedding_model": "gemini-embedding-001",
                        "matches": [],
                    },
                },
            },
        )(),
    )
    response = orchestrate_agent_v2_request(
        question="What is LangGraph?",
        filename="doc.txt",
        top_k=3,
    )
    assert response.route.route_type == "knowledge_retrieval"
    assert response.answer == "retrieved answer"
    assert response.workflow_planning_mode == "llm_openai"
    assert response.model == "gemini-2.5-flash"
    assert response.chat_provider == "gemini"
    assert response.chat_model == "gemini-2.5-flash"
    assert response.answer_latency_ms == 123.0
    assert response.answered_at == "2026-04-07T00:00:00+00:00"
    assert response.retrieval is not None
    assert response.retrieval.filename == "doc.txt"
    assert response.workflow_trace[-1].detail == "retrieved answer"


def test_orchestrate_agent_v2_request_finalizes_langsmith_trace(monkeypatch):
    captured = {}

    class StubTraceContext:
        def __enter__(self):
            captured["entered"] = True
            return "trace-run"

        def __exit__(self, exc_type, exc, tb):
            captured["exited"] = True
            return False

    def stub_trace_agent_v2_run(**kwargs):
        captured["trace_kwargs"] = kwargs
        return StubTraceContext()

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.trace_agent_v2_run",
        stub_trace_agent_v2_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.finalize_agent_v2_trace",
        lambda trace_run, *, response=None, error=None: captured.setdefault(
            "finalized",
            {"trace_run": trace_run, "response": response, "error": error},
        ),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "knowledge_retrieval",
                    "route_reason": "Knowledge question.",
                    "workflow_status": "completed",
                    "answer": "retrieved answer",
                    "answer_source": "fallback",
                    "tool_chain": [],
                },
            },
        )(),
    )

    response = orchestrate_agent_v2_request(question="What is LangGraph?", top_k=3)

    assert captured["trace_kwargs"]["operation"] == "orchestrate"
    assert captured["trace_kwargs"]["inputs"]["question"] == "What is LangGraph?"
    assert captured["finalized"]["trace_run"] == "trace-run"
    assert captured["finalized"]["response"] == response
    assert captured["finalized"]["error"] is None


def test_orchestrate_agent_v2_request_returns_clarification_response(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "clarification_needed",
                    "route_reason": "Ambiguous request.",
                    "route_planning_mode": "heuristic_legacy_router",
                    "__interrupt__": [
                        type(
                            "Interrupt",
                            (),
                            {
                                "value": {
                                    "clarification_question": "Could you clarify your question?",
                                    "clarification_plan": {
                                        "question": "Fix it",
                                        "planning_mode": "heuristic_stub",
                                        "missing_fields": ["task_details"],
                                        "follow_up_questions": ["What exact action should the agent perform?"],
                                        "clarification_summary": "Could you clarify your question?",
                                    },
                                }
                            },
                        )()
                    ],
                },
            },
        )(),
    )
    response = orchestrate_agent_v2_request(
        question="Fix it",
        filename=None,
        top_k=3,
    )
    assert response.workflow_status == "clarification_required"
    assert response.clarification_message == "Could you clarify your question?"
    assert response.clarification_plan is not None
    assert response.terminal_reason == "clarification_requested"
    assert response.recommended_recovery_action == "resume_with_clarification"
    assert response.available_recovery_actions == ["resume_with_clarification"]
    assert response.recovery_action_details == {
        "resume_with_clarification": {
            "missing_fields": ["task_details"],
        }
    }


def test_orchestrate_agent_v2_request_passes_thread_config_when_checkpointer_present(monkeypatch):
    captured = {}

    class StubGraph:
        def invoke(self, state, config=None):
            captured["config"] = config
            return {
                **state,
                "route": "knowledge_retrieval",
                "route_reason": "Knowledge question.",
                "route_planning_mode": "llm_openai",
                "workflow_status": "completed",
                "answer": "retrieved answer",
                "answer_source": "fallback",
                "model": "gemini-2.5-flash",
                "answered_at": "2026-04-07T00:00:00+00:00",
                "answer_latency_ms": 123.0,
                "chat_provider": "gemini",
                "chat_model": "gemini-2.5-flash",
                "retrieval_result": {
                    "filename": "doc.txt",
                    "embedding_provider": "gemini",
                    "embedding_model": "gemini-embedding-001",
                    "vector_dim": 3072,
                    "question": "What is LangGraph?",
                    "top_k": 3,
                    "retrieved_at": "2026-04-07T00:00:00+00:00",
                    "retrieval_latency_ms": 50.0,
                    "query_embedding_provider": "gemini",
                    "query_embedding_model": "gemini-embedding-001",
                    "matches": [],
                },
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    response = orchestrate_agent_v2_request(
        question="What is LangGraph?",
        filename="doc.txt",
        top_k=3,
        checkpointer=object(),
    )
    assert response.run_id
    assert captured["config"]["configurable"]["thread_id"] == response.run_id


def test_orchestrate_agent_v2_request_returns_tool_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "tool_execution",
                    "route_reason": "Execution request.",
                    "route_planning_mode": "llm_openai",
                    "workflow_status": "completed",
                    "answer": "Created ticket TICKET-0001 for payment-service.",
                    "answer_source": "tool_result",
                    "tool_chain": [
                        {
                            "step_id": "step_1",
                            "step_index": 1,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:00+00:00",
                            "completed_at": "2026-04-07T00:00:00+00:00",
                            "question": "Create a ticket for payment-service outage",
                            "tool_plan": {
                                "tool_name": "ticketing",
                                "action": "create",
                                "target": "payment-service",
                                "arguments": {"severity": "high"},
                            },
                            "tool_execution": {
                                "tool_name": "ticketing",
                                "action": "create",
                                "target": "payment-service",
                                "execution_status": "completed",
                                "result_summary": "Created ticket TICKET-0001 for payment-service.",
                            },
                        }
                    ],
                },
            },
        )(),
    )
    response = orchestrate_agent_v2_request(
        question="Create a ticket for payment-service outage",
        filename=None,
        top_k=3,
    )
    assert response.route.route_type == "tool_execution"
    assert response.answer == "Created ticket TICKET-0001 for payment-service."
    assert response.answer_source == "tool_result"
    assert response.tool_plan["tool_name"] == "ticketing"
    assert response.tool_execution["execution_status"] == "completed"
    assert response.workflow_trace[-1].detail == "Tool execution node completed in agent_v2."


def test_orchestrate_agent_v2_request_returns_incident_triage_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "tool_execution",
                    "route_reason": "Incident triage should inspect service health and prepare a ticket draft when needed.",
                    "route_planning_mode": "llm_gemini",
                    "workflow_status": "clarification_required",
                    "answer": "Incident triage prepared draft TICKET-0001 for payment-service.",
                    "answer_source": "local_incident_triage",
                    "clarification_question": "Draft TICKET-0001 is ready for payment-service in production. Do you want me to submit it?",
                    "clarification_plan": {
                        "confirmation_kind": "ticket_submission",
                        "ticket_id": "TICKET-0001",
                        "missing_fields": ["submission_confirmation"],
                    },
                    "tool_chain": [
                        {
                            "step_id": "step_1",
                            "step_index": 1,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:00+00:00",
                            "completed_at": "2026-04-07T00:00:01+00:00",
                            "question": state["question"],
                            "tool_plan": {"tool_name": "system_status", "action": "query", "target": "payment-service", "arguments": {"environment": "production"}},
                            "tool_execution": {"tool_name": "system_status", "action": "query", "execution_status": "completed", "result_summary": "status checked"},
                        },
                        {
                            "step_id": "step_2",
                            "step_index": 2,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:01+00:00",
                            "completed_at": "2026-04-07T00:00:02+00:00",
                            "question": state["question"],
                            "tool_plan": {"tool_name": "document_search", "action": "query", "target": "payment-service timeout", "arguments": {"max_results": "3"}},
                            "tool_execution": {"tool_name": "document_search", "action": "query", "execution_status": "completed", "result_summary": "docs searched"},
                        },
                        {
                            "step_id": "step_3",
                            "step_index": 3,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:02+00:00",
                            "completed_at": "2026-04-07T00:00:03+00:00",
                            "question": state["question"],
                            "tool_plan": {"tool_name": "ticketing", "action": "draft", "target": "payment-service", "arguments": {"severity": "high"}},
                            "tool_execution": {
                                "tool_name": "ticketing",
                                "action": "draft",
                                "target": "payment-service",
                                "execution_status": "completed",
                                "result_summary": "Prepared ticket draft TICKET-0001 for payment-service.",
                                "output": {"ticket_id": "TICKET-0001", "submission_state": "awaiting_user_confirmation"},
                            },
                        },
                    ],
                },
            },
        )(),
    )

    response = orchestrate_agent_v2_request(
        question="Check payment-service in production for timeout issues and if it is abnormal prepare a high severity ticket draft",
        top_k=3,
    )

    assert response.workflow_status == "clarification_required"
    assert response.terminal_reason == "clarification_requested"
    assert response.answer_source == "local_incident_triage"
    assert response.step_count == 3
    assert response.tool_execution["action"] == "draft"
    assert response.workflow_family == "incident_triage"
    assert [skill.skill_id for skill in response.available_skills] == [
        "review_service_health",
        "collect_incident_evidence",
        "prepare_incident_ticket",
    ]
    assert [skill.skill_id for skill in response.skill_trace] == [
        "review_service_health",
        "collect_incident_evidence",
        "prepare_incident_ticket",
    ]
    assert response.tool_chain[0].skill_id == "review_service_health"
    assert response.tool_chain[1].skill_id == "collect_incident_evidence"
    assert response.tool_chain[2].skill_id == "prepare_incident_ticket"
    assert response.recommended_recovery_action == "resume_with_clarification"
    assert response.clarification_plan["confirmation_kind"] == "ticket_submission"
    assert response.workflow_trace[-1].stage == "clarification"


def test_orchestrate_agent_v2_request_returns_service_runtime_review_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "tool_execution",
                    "route_reason": "Service runtime review should inspect current health and gather runbook guidance.",
                    "route_planning_mode": "llm_gemini",
                    "workflow_status": "completed",
                    "answer": "Service runtime review for payment-service in production found the service degraded. Service is degraded due to elevated timeout rate and downstream DB latency. Recommended checks: inspect active alerts timeout_rate_high, dependency_db_latency_spike. Likely dependency to inspect next: payment-db. Relevant guidance came from payment_service_runbook.md.",
                    "answer_source": "local_service_runtime_review",
                    "tool_chain": [
                        {
                            "step_id": "step_1",
                            "step_index": 1,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:00+00:00",
                            "completed_at": "2026-04-07T00:00:01+00:00",
                            "question": state["question"],
                            "tool_plan": {"tool_name": "system_status", "action": "query", "target": "payment-service", "arguments": {"environment": "production"}},
                            "tool_execution": {"tool_name": "system_status", "action": "query", "execution_status": "completed", "result_summary": "status checked"},
                        },
                        {
                            "step_id": "step_2",
                            "step_index": 2,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:01+00:00",
                            "completed_at": "2026-04-07T00:00:02+00:00",
                            "question": state["question"],
                            "tool_plan": {"tool_name": "service_dependencies", "action": "query", "target": "payment-service", "arguments": {"environment": "production", "failure_signal": "timeout_rate_high"}},
                            "tool_execution": {"tool_name": "service_dependencies", "action": "query", "execution_status": "completed", "result_summary": "dependency map loaded", "output": {"suspected_primary_dependency": "payment-db"}},
                        },
                        {
                            "step_id": "step_3",
                            "step_index": 3,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:02+00:00",
                            "completed_at": "2026-04-07T00:00:03+00:00",
                            "question": state["question"],
                            "tool_plan": {"tool_name": "document_search", "action": "query", "target": "timeout", "arguments": {"max_results": "3", "filename": "payment_service_runbook.md"}},
                            "tool_execution": {"tool_name": "document_search", "action": "query", "execution_status": "completed", "result_summary": "guidance searched"},
                        },
                    ],
                },
            },
        )(),
    )

    response = orchestrate_agent_v2_request(
        question="Check payment-service in production status and tell me what to look at for timeout issues",
        top_k=3,
    )

    assert response.workflow_status == "completed"
    assert response.answer_source == "local_service_runtime_review"
    assert response.workflow_family == "service_runtime_review"
    assert [skill.skill_id for skill in response.available_skills] == [
        "review_service_health",
        "inspect_service_dependencies",
        "collect_runtime_guidance",
    ]
    assert [skill.skill_id for skill in response.skill_trace] == [
        "review_service_health",
        "inspect_service_dependencies",
        "collect_runtime_guidance",
    ]
    assert response.tool_chain[0].skill_id == "review_service_health"
    assert response.tool_chain[1].skill_id == "inspect_service_dependencies"
    assert response.tool_chain[2].skill_id == "collect_runtime_guidance"
    assert response.workflow_trace[-1].stage == "tool_execution"
    assert "Service runtime review" in response.workflow_trace[-1].detail


def test_orchestrate_agent_v2_request_returns_failed_tool_response(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "tool_execution",
                    "route_reason": "Execution request.",
                    "workflow_status": "failed",
                    "failure_stage": "tool_execution",
                    "retry_state": "retry_exhausted",
                    "retry_count": 1,
                    "error": "debug injected persistent failure",
                    "tool_chain": [
                        {
                            "step_id": "step_1",
                            "step_index": 1,
                            "step_status": "failed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:00+00:00",
                            "completed_at": "2026-04-07T00:00:01+00:00",
                            "question": "Create a ticket",
                            "tool_plan": {
                                "tool_name": "ticketing",
                                "action": "create",
                                "target": "payment-service",
                                "arguments": {"severity": "high"},
                            },
                            "tool_execution": None,
                            "failure_message": "debug injected persistent failure",
                        }
                    ],
                },
            },
        )(),
    )
    response = orchestrate_agent_v2_request(
        question="Create a ticket for payment-service outage",
        top_k=3,
    )
    assert response.workflow_status == "failed"
    assert response.terminal_reason == "tool_execution_failed"
    assert response.outcome_category == "failed"
    assert response.retry_state == "retry_exhausted"
    assert response.recommended_recovery_action == "resume_from_failed_step"
    assert response.available_recovery_actions == ["resume_from_failed_step", "manual_retrigger"]
    assert response.failure_stage == "tool_execution"
    assert response.failure_message == "debug injected persistent failure"
    assert response.step_count == 1
    assert response.tool_chain[0].step_status == "failed"


def test_recover_agent_v2_request_manual_retriggers_failed_run(monkeypatch):
    from app.schemas.query import AgentWorkflowResponse, RouteDecision

    source_run = AgentWorkflowResponse(
        run_id="run-failed-123",
        question="Create a ticket for payment-service outage",
        workflow_status="failed",
        route=RouteDecision(
            route_type="tool_execution",
            route_reason="Execution request.",
            filename=None,
        ),
        failure_stage="tool_execution",
        failure_message="debug injected persistent failure",
        retry_state="retry_exhausted",
        retry_count=1,
        recommended_recovery_action="manual_retrigger",
        available_recovery_actions=["manual_retrigger"],
    )
    captured = {}

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: source_run,
    )

    def stub_execute(**kwargs):
        captured["kwargs"] = kwargs
        return AgentWorkflowResponse(
            run_id="rerun-123",
            root_run_id=kwargs["root_run_id"],
            recovery_depth=kwargs["recovery_depth"],
            question=kwargs["question"],
            source_run_id=kwargs["source_run_id"],
            recovered_via_action=kwargs["recovered_via_action"],
            resume_source_type=kwargs["resume_source_type"],
            resume_strategy=kwargs["resume_strategy"],
            workflow_status="completed",
            route=RouteDecision(
                route_type="tool_execution",
                route_reason="Retried from failure.",
                filename=None,
            ),
            answer="Recovered via manual retrigger",
            answer_source="tool_result",
        )

    monkeypatch.setattr(
        "app.services.agent_v2.query_service._execute_agent_v2_workflow",
        stub_execute,
    )

    response = recover_agent_v2_request(
        run_id="run-failed-123",
        recovery_action="manual_retrigger",
        clarification_context={},
        checkpointer=object(),
    )
    assert captured["kwargs"]["source_run_id"] == "run-failed-123"
    assert captured["kwargs"]["recovered_via_action"] == "manual_retrigger"
    assert captured["kwargs"]["resume_strategy"] == "manual_retrigger_recovery"
    assert captured["kwargs"]["recovery_depth"] == 1
    assert response.run_id == "rerun-123"


def test_recover_agent_v2_request_resumes_from_failed_step(monkeypatch):
    from app.schemas.query import AgentWorkflowResponse, RouteDecision

    source_run = AgentWorkflowResponse(
        run_id="run-failed-456",
        question="Create a ticket for payment-service outage",
        workflow_status="failed",
        route=RouteDecision(
            route_type="tool_execution",
            route_reason="Execution request.",
            filename=None,
        ),
        failure_stage="tool_execution",
        failure_message="debug injected persistent failure",
        retry_state="retry_exhausted",
        retry_count=1,
        recommended_recovery_action="resume_from_failed_step",
        available_recovery_actions=["resume_from_failed_step", "manual_retrigger"],
        tool_chain=[
            {
                "step_id": "step_1",
                "step_index": 1,
                "step_status": "failed",
                "attempt_count": 1,
                "retried": False,
                "started_at": "2026-04-07T00:00:00+00:00",
                "completed_at": "2026-04-07T00:00:01+00:00",
                "question": "Create a ticket for payment-service outage",
                "tool_plan": {
                    "tool_name": "ticketing",
                    "action": "create",
                    "target": "payment-service",
                    "arguments": {"severity": "high"},
                },
                "tool_execution": None,
                "failure_message": "debug injected persistent failure",
            }
        ],
    )
    captured = {}

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: source_run,
    )

    def stub_execute(**kwargs):
        captured["kwargs"] = kwargs
        return AgentWorkflowResponse(
            run_id="rerun-step-123",
            root_run_id=kwargs["root_run_id"],
            recovery_depth=kwargs["recovery_depth"],
            question=kwargs["question"],
            source_run_id=kwargs["source_run_id"],
            recovered_via_action=kwargs["recovered_via_action"],
            resume_source_type=kwargs["resume_source_type"],
            resume_strategy=kwargs["resume_strategy"],
            resumed_from_step_index=kwargs["resumed_from_step_index"],
            retried_step_indices=kwargs["retried_step_indices"],
            workflow_status="completed",
            route=RouteDecision(
                route_type="tool_execution",
                route_reason="Retried from failed step.",
                filename=None,
            ),
            answer="Recovered via failed-step resume",
            answer_source="tool_result",
        )

    monkeypatch.setattr(
        "app.services.agent_v2.query_service._execute_agent_v2_workflow",
        stub_execute,
    )

    response = recover_agent_v2_request(
        run_id="run-failed-456",
        recovery_action="resume_from_failed_step",
        clarification_context={},
        checkpointer=object(),
    )
    assert captured["kwargs"]["recovered_via_action"] == "resume_from_failed_step"
    assert captured["kwargs"]["resume_strategy"] == "failed_step_resume"
    assert captured["kwargs"]["resumed_from_step_index"] == 1
    assert captured["kwargs"]["retried_step_indices"] == [1]
    assert response.run_id == "rerun-step-123"


def test_recover_agent_v2_request_marks_clarification_recovery_metadata(monkeypatch):
    from app.schemas.query import AgentWorkflowResponse, RouteDecision

    resumed_response = AgentWorkflowResponse(
        run_id="run-clarify-123",
        question="Fix it (environment: production; task details: check system status for payment-service)",
        workflow_status="completed",
        route=RouteDecision(
            route_type="tool_execution",
            route_reason="Clarification applied.",
            filename=None,
        ),
        answer="Recovered via clarification",
        answer_source="tool_result",
    )
    persisted: dict[str, AgentWorkflowResponse] = {}

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.resume_agent_v2_request",
        lambda run_id, clarification_context=None, checkpointer=None: resumed_response,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: persisted.setdefault("response", response),
    )

    response = recover_agent_v2_request(
        run_id="run-clarify-123",
        recovery_action="resume_with_clarification",
        clarification_context={
            "environment": "production",
            "task_details": "check system status for payment-service",
        },
        checkpointer=object(),
    )

    assert response.recovered_via_action == "resume_with_clarification"
    assert response.resume_source_type == "run_id"
    assert response.resume_strategy == "clarification_recovery"
    assert persisted["response"].recovered_via_action == "resume_with_clarification"


def test_resume_agent_v2_request_submits_ticket_after_confirmation(monkeypatch):
    from app.services.agent_v2.query_service import resume_agent_v2_request
    from app.schemas.query import AgentWorkflowResponse, RouteDecision, WorkflowTraceEvent, WorkflowStepRecord

    persisted_run = AgentWorkflowResponse(
        run_id="run-ticket-confirm",
        question="Check payment-service in production for timeout issues and if it is abnormal prepare a high severity ticket draft",
        workflow_status="clarification_required",
        route=RouteDecision(
            route_type="tool_execution",
            route_reason="Incident triage should inspect service health and prepare a ticket draft when needed.",
            filename=None,
        ),
        answer="Incident triage prepared draft TICKET-0001 for payment-service.",
        answer_source="local_incident_triage",
        clarification_message="Draft TICKET-0001 is ready for payment-service in production. Do you want me to submit it?",
        clarification_plan={
            "confirmation_kind": "ticket_submission",
            "ticket_id": "TICKET-0001",
            "service": "payment-service",
            "environment": "production",
            "missing_fields": ["submission_confirmation"],
        },
        tool_plan={"tool_name": "ticketing", "action": "draft", "target": "payment-service"},
        tool_execution={"tool_name": "ticketing", "action": "draft", "target": "payment-service", "output": {"ticket_id": "TICKET-0001"}},
        tool_chain=[
            WorkflowStepRecord(
                step_id="step_3",
                step_index=3,
                step_status="completed",
                attempt_count=1,
                retried=False,
                started_at="2026-04-07T00:00:00+00:00",
                completed_at="2026-04-07T00:00:01+00:00",
                question="q",
                tool_plan={"tool_name": "ticketing", "action": "draft", "target": "payment-service"},
                tool_execution={"tool_name": "ticketing", "action": "draft", "target": "payment-service", "output": {"ticket_id": "TICKET-0001"}},
            )
        ],
        workflow_trace=[
            WorkflowTraceEvent(
                stage="clarification",
                status="clarification_required",
                timestamp="2026-04-07T00:00:01+00:00",
                detail="Draft TICKET-0001 is ready for payment-service in production. Do you want me to submit it?",
            )
        ],
    )

    persisted = {}
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: persisted.setdefault("response", response),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_utc_timestamp",
        lambda: "2026-04-07T00:00:02+00:00",
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.execute_tool_request",
        lambda request: type(
            "ToolExecution",
            (),
            {
                "execution_status": "completed",
                "executed_at": "2026-04-07T00:00:02+00:00",
                "model_dump": lambda self=None: {
                    "tool_name": "ticketing",
                    "action": "submit",
                    "target": "payment-service",
                    "execution_status": "completed",
                    "result_summary": "Submitted ticket draft TICKET-0001 for payment-service.",
                    "output": {"ticket_id": "TICKET-0001", "submission_state": "submitted"},
                },
            },
        )(),
    )

    response = resume_agent_v2_request(
        run_id="run-ticket-confirm",
        clarification_context={"submission_confirmation": "yes"},
        checkpointer=object(),
    )

    assert response.workflow_status == "completed"
    assert response.terminal_reason == "ticket_submitted"
    assert response.tool_execution["action"] == "submit"
    assert response.step_count == 2
    assert response.applied_clarification_fields == ["submission_confirmation"]
    assert persisted["response"].terminal_reason == "ticket_submitted"


def test_resume_agent_v2_request_cancels_ticket_when_confirmation_declined(monkeypatch):
    from app.services.agent_v2.query_service import resume_agent_v2_request
    from app.schemas.query import AgentWorkflowResponse, RouteDecision

    persisted_run = AgentWorkflowResponse(
        run_id="run-ticket-cancel",
        question="Check payment-service in production for timeout issues and if it is abnormal prepare a high severity ticket draft",
        workflow_status="clarification_required",
        route=RouteDecision(
            route_type="tool_execution",
            route_reason="Incident triage should inspect service health and prepare a ticket draft when needed.",
            filename=None,
        ),
        answer="Incident triage prepared draft TICKET-0002 for payment-service.",
        answer_source="local_incident_triage",
        clarification_message="Draft TICKET-0002 is ready for payment-service in production. Do you want me to submit it?",
        clarification_plan={
            "confirmation_kind": "ticket_submission",
            "ticket_id": "TICKET-0002",
            "service": "payment-service",
            "environment": "production",
            "missing_fields": ["submission_confirmation"],
        },
        tool_plan={"tool_name": "ticketing", "action": "draft", "target": "payment-service"},
        tool_execution={"tool_name": "ticketing", "action": "draft", "target": "payment-service", "output": {"ticket_id": "TICKET-0002"}},
    )

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_utc_timestamp",
        lambda: "2026-04-07T00:00:03+00:00",
    )

    response = resume_agent_v2_request(
        run_id="run-ticket-cancel",
        clarification_context={"submission_confirmation": "no"},
        checkpointer=object(),
    )

    assert response.workflow_status == "completed"
    assert response.terminal_reason == "ticket_submission_cancelled"
    assert response.answer == "Left ticket draft TICKET-0002 unsubmitted at operator request."


def test_stream_agent_v2_request_emits_updates_and_final_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.trace_agent_v2_run",
        lambda **kwargs: type(
            "TraceContext",
            (),
            {
                "__enter__": lambda self: "stream-trace",
                "__exit__": lambda self, exc_type, exc, tb: False,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.finalize_agent_v2_trace",
        lambda trace_run, *, response=None, error=None: None,
    )

    class StubGraph:
        def stream(self, state, config=None, stream_mode=None):
            assert stream_mode == "updates"
            yield {
                "router": {
                    "route": "tool_execution",
                    "route_reason": "Execution request.",
                    "route_planning_mode": "llm_openai",
                    "workflow_status": "in_progress",
                }
            }
            yield {
                "supervisor": {
                    "supervisor_agent": "operations_specialist",
                    "supervisor_reason": "Supervisor delegated tool_execution to operations_specialist based on the current route decision.",
                    "workflow_status": "in_progress",
                }
            }
            yield {
                "operations_specialist": {
                    "tool_chain": [
                        {
                            "step_id": "step_1",
                            "step_index": 1,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:00+00:00",
                            "completed_at": "2026-04-07T00:00:01+00:00",
                            "question": "Create a ticket",
                            "tool_plan": {
                                "tool_name": "ticketing",
                                "action": "create",
                                "target": "payment-service",
                                "arguments": {"severity": "high"},
                            },
                            "tool_execution": {
                                "tool_name": "ticketing",
                                "action": "create",
                                "target": "payment-service",
                                "execution_status": "completed",
                                "result_summary": "Created ticket TICKET-0001 for payment-service.",
                            },
                        }
                    ],
                    "answer": "Created ticket TICKET-0001 for payment-service.",
                    "answer_source": "tool_result",
                    "workflow_status": "completed",
                }
            }
            yield {
                "answer": {
                    "answer": "Created ticket TICKET-0001 for payment-service.",
                    "answer_source": "tool_result",
                    "workflow_status": "completed",
                }
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )

    events = list(
        stream_agent_v2_request(
            question="Create a ticket",
            filename=None,
            top_k=3,
        )
    )

    assert events[0]["stage"] == "start"
    assert events[1]["stage"] == "routing"
    assert events[2]["stage"] == "supervisor"
    assert events[3]["stage"] == "operations_specialist"
    assert events[-2]["stage"] == "workflow"
    assert events[-1]["event_type"] == "result"
    assert events[-1]["response"]["answer"] == "Created ticket TICKET-0001 for payment-service."


def test_resume_agent_v2_request_rehydrates_from_checkpoint(monkeypatch):
    from app.schemas.query import RouteDecision, AgentWorkflowResponse
    from app.services.agent_v2.query_service import resume_agent_v2_request

    persisted_run = AgentWorkflowResponse(
        run_id="run-123",
        question="What is LangGraph?",
        workflow_status="completed",
        route=RouteDecision(
            route_type="knowledge_retrieval",
            route_reason="Knowledge question.",
            filename="doc.txt",
        ),
        answer="old answer",
        answer_source="fallback",
        model="gemini-2.5-flash",
        answered_at="2026-04-07T00:00:00+00:00",
        answer_latency_ms=123.0,
        chat_provider="gemini",
        chat_model="gemini-2.5-flash",
        filename="doc.txt",
        started_at="2026-04-07T00:00:00+00:00",
        completed_at="2026-04-07T00:00:00+00:00",
        last_updated_at="2026-04-07T00:00:00+00:00",
    )

    class StubSnapshot:
        values = {
            "question": "What is LangGraph?",
            "filename": "doc.txt",
            "route": "knowledge_retrieval",
            "route_reason": "Knowledge question.",
            "workflow_status": "completed",
            "answer": "resumed answer",
            "answer_source": "fallback",
            "model": "gemini-2.5-flash",
            "answered_at": "2026-04-07T00:00:01+00:00",
            "answer_latency_ms": 99.0,
            "chat_provider": "gemini",
            "chat_model": "gemini-2.5-flash",
            "retrieval_result": None,
            "tool_chain": [],
        }

    class StubGraph:
        def get_state(self, config):
            return StubSnapshot()

        def invoke(self, payload, config=None):
            assert payload is None
            return dict(StubSnapshot.values)

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )

    response = resume_agent_v2_request(run_id="run-123", checkpointer=object())
    assert response.run_id == "run-123"
    assert response.resume_source_type == "run_id"
    assert response.resume_strategy == "checkpoint_resume"
    assert response.answer == "resumed answer"
    assert response.completed_at == "2026-04-07T00:00:00+00:00"


def test_resume_agent_v2_request_sets_completed_at_when_source_run_was_incomplete(monkeypatch):
    from app.schemas.query import RouteDecision, AgentWorkflowResponse
    from app.services.agent_v2.query_service import resume_agent_v2_request

    persisted_run = AgentWorkflowResponse(
        run_id="run-456",
        question="What is LangGraph?",
        workflow_status="in_progress",
        route=RouteDecision(
            route_type="knowledge_retrieval",
            route_reason="Knowledge question.",
            filename="doc.txt",
        ),
        answer=None,
        answer_source=None,
        filename="doc.txt",
        started_at="2026-04-07T00:00:00+00:00",
        completed_at=None,
        last_updated_at="2026-04-07T00:00:00+00:00",
    )

    class StubSnapshot:
        values = {
            "question": "What is LangGraph?",
            "filename": "doc.txt",
        }

    class StubGraph:
        def get_state(self, config):
            return StubSnapshot()

        def invoke(self, payload, config=None):
            assert payload is None
            return {
                "question": "What is LangGraph?",
                "filename": "doc.txt",
                "route": "knowledge_retrieval",
                "route_reason": "Knowledge question.",
                "workflow_status": "completed",
                "answer": "resumed answer",
                "answer_source": "fallback",
                "tool_chain": [],
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_utc_timestamp",
        lambda: "2026-04-07T00:05:00+00:00",
    )

    response = resume_agent_v2_request(run_id="run-456", checkpointer=object())
    assert response.completed_at == "2026-04-07T00:05:00+00:00"
    assert response.last_updated_at == "2026-04-07T00:05:00+00:00"


def test_resume_agent_v2_request_uses_command_resume_for_clarification(monkeypatch):
    from app.schemas.query import RouteDecision, AgentWorkflowResponse
    from app.services.agent_v2.query_service import resume_agent_v2_request

    persisted_run = AgentWorkflowResponse(
        run_id="run-789",
        question="Fix it",
        workflow_status="clarification_required",
        route=RouteDecision(
            route_type="clarification_needed",
            route_reason="Ambiguous request.",
            filename=None,
        ),
        clarification_message="Could you clarify your question?",
        clarification_plan={
            "question": "Fix it",
            "planning_mode": "heuristic_stub",
            "missing_fields": ["task_details"],
            "follow_up_questions": ["What exact action should the agent perform?"],
            "clarification_summary": "Could you clarify your question?",
        },
        started_at="2026-04-07T00:00:00+00:00",
        last_updated_at="2026-04-07T00:00:00+00:00",
    )
    captured = {}

    class StubSnapshot:
        values = {"question": "Fix it"}

    class StubGraph:
        def get_state(self, config):
            return StubSnapshot()

        def invoke(self, payload, config=None):
            captured["payload"] = payload
            return {
                "question": "Fix it (environment: production)",
                "filename": "",
                "route": "knowledge_retrieval",
                "route_reason": "Now specific enough.",
                "workflow_status": "completed",
                "answer": "resolved answer",
                "answer_source": "fallback",
                "applied_clarification_fields": ["environment"],
                "question_rewritten": True,
                "tool_chain": [],
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )

    response = resume_agent_v2_request(
        run_id="run-789",
        clarification_context={"environment": "production"},
        checkpointer=object(),
    )
    assert isinstance(captured["payload"], Command)
    assert captured["payload"].resume == {"environment": "production"}
    assert response.answer == "resolved answer"
    assert response.applied_clarification_fields == ["environment"]
    assert response.question_rewritten is True
    assert response.recommended_recovery_action == "none"
    assert response.available_recovery_actions == []


def test_resume_agent_v2_request_finalizes_langsmith_trace(monkeypatch):
    from app.schemas.query import RouteDecision, AgentWorkflowResponse
    from app.services.agent_v2.query_service import resume_agent_v2_request

    persisted_run = AgentWorkflowResponse(
        run_id="run-trace",
        question="Fix it",
        workflow_status="clarification_required",
        route=RouteDecision(
            route_type="clarification_needed",
            route_reason="Ambiguous request.",
            filename=None,
        ),
        clarification_message="Could you clarify your question?",
        started_at="2026-04-07T00:00:00+00:00",
        last_updated_at="2026-04-07T00:00:00+00:00",
    )
    captured = {}

    class StubSnapshot:
        values = {"question": "Fix it"}

    class StubTraceContext:
        def __enter__(self):
            return "resume-trace"

        def __exit__(self, exc_type, exc, tb):
            return False

    def stub_trace_agent_v2_run(**kwargs):
        captured["trace_kwargs"] = kwargs
        return StubTraceContext()

    class StubGraph:
        def get_state(self, config):
            return StubSnapshot()

        def invoke(self, payload, config=None):
            return {
                "question": "Fix it (environment: production)",
                "route": "tool_execution",
                "route_reason": "Specific enough.",
                "workflow_status": "completed",
                "answer": "resolved answer",
                "answer_source": "tool_result",
                "tool_chain": [],
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.trace_agent_v2_run",
        stub_trace_agent_v2_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.finalize_agent_v2_trace",
        lambda trace_run, *, response=None, error=None: captured.setdefault(
            "finalized",
            {"trace_run": trace_run, "response": response, "error": error},
        ),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )

    response = resume_agent_v2_request(
        run_id="run-trace",
        clarification_context={"environment": "production"},
        checkpointer=object(),
    )

    assert captured["trace_kwargs"]["operation"] == "resume"
    assert captured["trace_kwargs"]["inputs"]["run_id"] == "run-trace"
    assert captured["trace_kwargs"]["inputs"]["clarification_context_keys"] == ["environment"]
    assert captured["finalized"]["trace_run"] == "resume-trace"
    assert captured["finalized"]["response"] == response
    assert captured["finalized"]["error"] is None
