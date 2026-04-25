from app.services.agent_v2.skills.incident_triage import (
    build_incident_triage_summary,
    run_collect_incident_evidence_skill,
    run_prepare_incident_ticket_skill,
    run_review_service_health_skill,
)


BASE_STATE = {
    "question": "Check payment-service in production for timeout issues and if it is abnormal prepare a high severity ticket draft",
    "filename": "",
    "top_k": 3,
    "debug_fault_injection": {},
    "route": "tool_execution",
    "route_reason": "Tool request.",
    "route_planning_mode": "llm_openai",
    "retrieval_result": None,
    "tool_chain": [],
    "clarification_question": None,
    "clarification_plan": None,
    "applied_clarification_fields": [],
    "question_rewritten": False,
    "answer": None,
    "answer_source": None,
    "workflow_status": "in_progress",
    "failure_stage": None,
    "retry_state": None,
    "retry_count": 0,
    "error": None,
    "messages": [],
}


def test_incident_triage_skills_execute_reusable_phases():
    calls: list[tuple[int, str, str]] = []

    def execute_step(**kwargs):
        step_index = kwargs["step_index"]
        tool_name = kwargs["tool_name"]
        calls.append((step_index, tool_name, kwargs["target"]))
        output_by_step = {
            1: {
                "health": "degraded",
                "summary": "Service is degraded due to elevated timeout rate and downstream DB latency.",
                "service_record": {"runbook_doc_ids": ["payment_service_runbook.md"]},
            },
            2: {
                "matched_documents": "payment_service_runbook.md",
            },
            3: {
                "matched_documents": "customer_support_tickets_7.md, customer_support_tickets_2.md",
            },
            4: {
                "ticket_id": "TICKET-0001",
                "status": "draft",
                "submission_state": "awaiting_user_confirmation",
            },
        }
        return (
            {
                "step_id": f"step_{step_index}",
                "step_index": step_index,
                "tool_plan": {
                    "tool_name": tool_name,
                    "action": kwargs["action"],
                    "target": kwargs["target"],
                    "arguments": kwargs["arguments"],
                    "planning_mode": kwargs["planning_mode"],
                },
                "tool_execution": {"output": output_by_step[step_index]},
            },
            type(
                "ToolExecution",
                (),
                {"model_dump": lambda self=None: {"output": output_by_step[step_index]}},
            )(),
        )

    status_steps, status_output = run_review_service_health_skill(
        state=BASE_STATE,
        question=BASE_STATE["question"],
        service="payment-service",
        environment="production",
        symptom="timeout",
        planning_mode="agent_v2_incident_triage",
        execute_step=execute_step,
    )
    evidence_steps, search_output, external_output = run_collect_incident_evidence_skill(
        state=BASE_STATE,
        question=BASE_STATE["question"],
        service="payment-service",
        environment="production",
        symptom="timeout",
        status_output=status_output,
        execute_step=execute_step,
    )
    ticket_steps, draft_output, clarification_question, clarification_plan = run_prepare_incident_ticket_skill(
        state=BASE_STATE,
        question=BASE_STATE["question"],
        service="payment-service",
        environment="production",
        severity="high",
        symptom="timeout",
        status_output=status_output,
        external_search_output=external_output,
        execute_step=execute_step,
    )

    assert calls == [
        (1, "system_status", "payment-service"),
        (2, "document_search", "timeout"),
        (3, "document_search", "payment-service production timeout Service is degraded due to elevated timeout rate and downstream DB latency."),
        (4, "ticketing", "payment-service"),
    ]
    assert len(status_steps) == 1
    assert status_steps[0]["tool_plan"]["planning_mode"] == "agent_v2_incident_triage"
    assert len(evidence_steps) == 2
    assert len(ticket_steps) == 1
    assert search_output["matched_documents"] == "payment_service_runbook.md"
    assert draft_output["ticket_id"] == "TICKET-0001"
    assert clarification_plan["confirmation_kind"] == "ticket_submission"
    assert clarification_question.startswith("Draft TICKET-0001 is ready")
    assert "likely timeout issue" in build_incident_triage_summary(
        service="payment-service",
        environment="production",
        symptom="timeout",
        status_output=status_output,
        search_output={
            "matched_documents": "payment_service_runbook.md, customer_support_tickets_7.md",
        },
        draft_output=draft_output,
    )
