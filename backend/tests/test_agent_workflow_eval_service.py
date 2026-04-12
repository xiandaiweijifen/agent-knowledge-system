import json

from app.schemas.query import AgentWorkflowResponse, RouteDecision, WorkflowTraceEvent
from app.services.evaluation.agent_workflow_eval_service import evaluate_agent_workflow_dataset


def _build_tool_chain_step(
    *,
    question: str,
    tool_name: str,
    action: str,
    tool_execution: dict | None = None,
    step_status: str = "completed",
) -> dict:
    return {
        "step_id": "step_1",
        "step_index": 1,
        "step_status": step_status,
        "attempt_count": 1,
        "retried": False,
        "started_at": "2026-04-12T00:00:00+00:00",
        "completed_at": "2026-04-12T00:00:01+00:00",
        "question": question,
        "tool_plan": {"tool_name": tool_name, "action": action},
        "tool_execution": tool_execution,
        "failure_message": None,
    }


def _build_response(
    *,
    question: str,
    route_type: str,
    workflow_status: str,
    route_reason: str = "selected by test",
    filename: str | None = None,
    recovered_via_action: str | None = None,
    resume_source_type: str | None = None,
    resume_strategy: str | None = None,
    tool_plan: dict | None = None,
    tool_execution: dict | None = None,
    tool_chain: list[dict] | None = None,
) -> AgentWorkflowResponse:
    return AgentWorkflowResponse(
        question=question,
        workflow_status=workflow_status,
        route=RouteDecision(
            route_type=route_type,
            route_reason=route_reason,
            filename=filename,
        ),
        workflow_trace=[
            WorkflowTraceEvent(
                stage="routing",
                status="completed",
                timestamp="2026-04-12T00:00:00+00:00",
                detail=f"Route selected: {route_type}",
            )
        ],
        filename=filename,
        recovered_via_action=recovered_via_action,
        resume_source_type=resume_source_type,
        resume_strategy=resume_strategy,
        tool_plan=tool_plan,
        tool_execution=tool_execution,
        tool_chain=tool_chain or [],
    )


def test_evaluate_agent_workflow_dataset_uses_agent_v2_semantics(workspace_tmp_path, monkeypatch):
    dataset_path = workspace_tmp_path / "agent_workflow_eval.json"
    dataset_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "knowledge_case",
                        "question": "What is RAG?",
                        "filename": "rag_overview.md",
                        "expected_route_type": "knowledge_retrieval",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "tool_case",
                        "question": "Create a high severity ticket for payment-service outage",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "ticketing",
                        "expected_final_action": "create",
                        "expected_final_output_keys": ["ticket_id", "status"],
                    },
                    {
                        "case_id": "clarification_case",
                        "question": "Fix it",
                        "expected_route_type": "clarification_needed",
                        "expected_workflow_status": "clarification_required",
                    },
                    {
                        "case_id": "clarification_resume_case",
                        "question": "Fix it",
                        "clarification_context": {
                            "environment": "production",
                            "task_details": "check system status for payment-service",
                        },
                        "resume_via_run_id": True,
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_question": "Fix it (environment: production; task details: check system status for payment-service)",
                        "expected_resume_trace": True,
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "system_status",
                        "expected_final_action": "query",
                        "expected_final_output_keys": ["status", "requested_environment"],
                    },
                    {
                        "case_id": "failed_step_recovery_case",
                        "question": "Create a high severity ticket for payment-service outage",
                        "recovery_action": "resume_from_failed_step",
                        "debug_fault_injection": {
                            "tool_execution_failures": [
                                {
                                    "tool_name": "ticketing",
                                    "action": "create",
                                    "fail_count": 1,
                                    "message": "debug injected persistent failure",
                                }
                            ]
                        },
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_resume_trace": True,
                        "expected_recovered_via_action": "resume_from_failed_step",
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "ticketing",
                        "expected_final_action": "create",
                        "expected_final_output_keys": ["ticket_id", "status"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_orchestrate(question: str, filename=None, top_k=3, debug_fault_injection=None):
        if question == "What is RAG?":
            return _build_response(
                question=question,
                filename=filename,
                route_type="knowledge_retrieval",
                workflow_status="completed",
            )
        if question == "Create a high severity ticket for payment-service outage":
            if debug_fault_injection:
                return _build_response(
                    question=question,
                    route_type="tool_execution",
                    workflow_status="failed",
                    tool_plan={
                        "tool_name": "ticketing",
                        "action": "create",
                    },
                    tool_chain=[
                        _build_tool_chain_step(
                            question=question,
                            tool_name="ticketing",
                            action="create",
                            tool_execution=None,
                            step_status="failed",
                        )
                    ],
                ).model_copy(update={"run_id": "failed-run"})
            return _build_response(
                question=question,
                route_type="tool_execution",
                workflow_status="completed",
                tool_plan={"tool_name": "ticketing", "action": "create"},
                tool_execution={
                    "tool_name": "ticketing",
                    "action": "create",
                    "output": {"ticket_id": "TICKET-0001", "status": "open"},
                },
                tool_chain=[
                    _build_tool_chain_step(
                        question=question,
                        tool_name="ticketing",
                        action="create",
                        tool_execution={"tool_name": "ticketing", "action": "create"},
                    )
                ],
            )
        if question == "Fix it":
            return _build_response(
                question=question,
                route_type="clarification_needed",
                workflow_status="clarification_required",
            ).model_copy(update={"run_id": "clarify-run"})
        raise AssertionError(f"unexpected question: {question}")

    def fake_resume(run_id: str, clarification_context: dict[str, str]):
        assert run_id == "clarify-run"
        assert clarification_context["environment"] == "production"
        return _build_response(
            question="Fix it (environment: production; task details: check system status for payment-service)",
            route_type="tool_execution",
            workflow_status="completed",
            resume_source_type="run_id",
            resume_strategy="checkpoint_resume",
            tool_plan={"tool_name": "system_status", "action": "query"},
            tool_execution={
                "tool_name": "system_status",
                "action": "query",
                "output": {"status": "ok", "requested_environment": "production"},
            },
            tool_chain=[
                _build_tool_chain_step(
                    question="Fix it (environment: production; task details: check system status for payment-service)",
                    tool_name="system_status",
                    action="query",
                    tool_execution={"tool_name": "system_status", "action": "query"},
                )
            ],
        )

    def fake_recover(run_id: str, recovery_action: str | None, clarification_context=None, debug_fault_injection=None):
        if recovery_action == "resume_with_clarification":
            return fake_resume(run_id=run_id, clarification_context=clarification_context or {})
        assert run_id == "failed-run"
        assert recovery_action == "resume_from_failed_step"
        return _build_response(
            question="Create a high severity ticket for payment-service outage",
            route_type="tool_execution",
            workflow_status="completed",
            recovered_via_action="resume_from_failed_step",
            resume_source_type="run_id",
            resume_strategy="failed_step_resume",
            tool_plan={"tool_name": "ticketing", "action": "create"},
            tool_execution={
                "tool_name": "ticketing",
                "action": "create",
                "output": {"ticket_id": "TICKET-0002", "status": "open"},
            },
            tool_chain=[
                _build_tool_chain_step(
                    question="Create a high severity ticket for payment-service outage",
                    tool_name="ticketing",
                    action="create",
                    tool_execution={"tool_name": "ticketing", "action": "create"},
                )
            ],
        )

    monkeypatch.setattr(
        "app.services.evaluation.agent_workflow_eval_service.orchestrate_agent_v2_request",
        fake_orchestrate,
    )
    monkeypatch.setattr(
        "app.services.evaluation.agent_workflow_eval_service.resume_agent_v2_request",
        fake_resume,
    )
    monkeypatch.setattr(
        "app.services.evaluation.agent_workflow_eval_service.recover_agent_v2_request",
        fake_recover,
    )

    report = evaluate_agent_workflow_dataset(dataset_path=dataset_path)

    assert report.summary.total_cases == 5
    assert report.summary.workflow_accuracy == 1.0
    assert all(case.matched for case in report.cases)
    resumed_case = next(case for case in report.cases if case.case_id == "clarification_resume_case")
    assert resumed_case.resume_trace_present is True
    assert resumed_case.actual_final_tool_name == "system_status"
    failed_step_case = next(case for case in report.cases if case.case_id == "failed_step_recovery_case")
    assert failed_step_case.actual_recovered_via_action == "resume_from_failed_step"
    assert failed_step_case.resume_trace_present is True
    assert failed_step_case.final_output_key_matches["ticket_id"] is True
