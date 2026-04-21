"""Tool execution node — runs tool actions requested by the router."""

import re

from app.schemas.tools import ToolExecutionRequest
from app.services.agent.tool_service import execute_tool_request, plan_tool_request
from app.services.agent_v2.state import AgentState
from app.services.ingestion.document_service import build_utc_timestamp


INCIDENT_TRIAGE_PATTERN = re.compile(
    r"\b(check|inspect|investigate|look at)\b.*\b(if|when)\b.*\b(abnormal|degraded|issue|incident)\b.*\b(ticket|draft|prepare)\b",
    re.IGNORECASE,
)
SERVICE_PATTERN = re.compile(r"\b([a-z0-9][a-z0-9-]*(?:service|api))\b", re.IGNORECASE)
ENVIRONMENT_PATTERN = re.compile(r"\b(production|staging|development|dev)\b", re.IGNORECASE)
SEVERITY_PATTERN = re.compile(r"\b(high|medium|low)\s+severity\b", re.IGNORECASE)
SYMPTOM_PATTERN = re.compile(
    r"\b(timeout|latency|5xx|502|error rate|errors|outage|incident)\b",
    re.IGNORECASE,
)


def _normalize_environment(environment: str | None) -> str:
    if not environment:
        return "production"
    lowered = environment.lower()
    if lowered == "dev":
        return "development"
    return lowered


def _extract_incident_triage_context(question: str) -> dict[str, str] | None:
    if not INCIDENT_TRIAGE_PATTERN.search(question):
        return None

    service_match = SERVICE_PATTERN.search(question)
    if service_match is None:
        return None

    environment_match = ENVIRONMENT_PATTERN.search(question)
    severity_match = SEVERITY_PATTERN.search(question)
    symptom_match = SYMPTOM_PATTERN.search(question)
    return {
        "service": service_match.group(1),
        "environment": _normalize_environment(environment_match.group(1) if environment_match else None),
        "severity": (severity_match.group(1).lower() if severity_match else "high"),
        "symptom": (symptom_match.group(1).lower() if symptom_match else "incident"),
    }


def _build_step_record(
    *,
    step_index: int,
    question: str,
    started_at: str,
    tool_plan: dict,
    tool_execution,
    failure_message: str | None = None,
) -> dict:
    return {
        "step_id": f"step_{step_index}",
        "step_index": step_index,
        "step_status": tool_execution.execution_status if tool_execution is not None else "failed",
        "attempt_count": 1,
        "retried": False,
        "started_at": started_at,
        "completed_at": (tool_execution.executed_at if tool_execution is not None else build_utc_timestamp()),
        "question": question,
        "tool_plan": tool_plan,
        "tool_execution": tool_execution.model_dump() if tool_execution is not None else None,
        "failure_message": failure_message,
    }


def _get_matching_fault_rule(state: AgentState, tool_name: str, action: str) -> dict | None:
    debug_fault_injection = state.get("debug_fault_injection") or {}
    rules = debug_fault_injection.get("tool_execution_failures", [])
    if not isinstance(rules, list):
        return None

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("tool_name") != tool_name:
            continue
        if rule.get("action") != action:
            continue
        if int(rule.get("fail_count", 0) or 0) <= 0:
            continue
        return rule
    return None


def _execute_single_step(
    *,
    state: AgentState,
    step_index: int,
    question: str,
    tool_name: str,
    action: str,
    target: str,
    arguments: dict[str, str],
    planning_mode: str,
) -> tuple[dict, object]:
    fault_rule = _get_matching_fault_rule(state, tool_name, action)
    if fault_rule is not None:
        raise RuntimeError(str(fault_rule.get("message") or "debug injected tool execution failure"))

    started_at = build_utc_timestamp()
    tool_execution = execute_tool_request(
        ToolExecutionRequest(
            tool_name=tool_name,
            action=action,
            target=target,
            arguments=arguments,
        )
    )
    return (
        _build_step_record(
            step_index=step_index,
            question=question,
            started_at=started_at,
            tool_plan={
                "question": question,
                "planning_mode": planning_mode,
                "route_hint": "tool_execution",
                "tool_name": tool_name,
                "action": action,
                "target": target,
                "arguments": arguments,
                "plan_summary": f"Plan {tool_name}:{action} for {target}.",
            },
            tool_execution=tool_execution,
        ),
        tool_execution,
    )


def _build_incident_triage_summary(
    *,
    service: str,
    environment: str,
    symptom: str,
    status_output: dict,
    search_output: dict | None,
    draft_output: dict | None,
) -> str:
    status_summary = status_output.get("summary") or f"{service} status checked in {environment}."
    if draft_output is None:
        return (
            f"Incident triage for {service} in {environment} found no ticket-worthy issue. "
            f"{status_summary}"
        )

    matched_documents = ""
    if isinstance(search_output, dict):
        matched_documents = str(search_output.get("matched_documents") or "").strip()
    document_clause = f" Supporting evidence came from {matched_documents}." if matched_documents else ""
    return (
        f"Incident triage for {service} in {environment} found a likely {symptom} issue. "
        f"{status_summary} Prepared ticket draft {draft_output.get('ticket_id', 'unknown')} for operator review."
        f"{document_clause}"
    )


def _build_external_evidence_query(
    *,
    service: str,
    environment: str,
    symptom: str,
    status_output: dict,
) -> str:
    alerts = status_output.get("active_alerts")
    alert_text = " ".join(str(item) for item in alerts if str(item).strip()) if isinstance(alerts, list) else ""
    status_summary = str(status_output.get("summary") or "")
    return " ".join(
        part
        for part in [service, environment, symptom, alert_text, status_summary]
        if part.strip()
    ).strip()


def _build_ticket_submission_confirmation(
    *,
    service: str,
    environment: str,
    draft_output: dict,
) -> tuple[str, dict]:
    ticket_id = str(draft_output.get("ticket_id") or "unknown").strip()
    confirmation_question = (
        f"Draft {ticket_id} is ready for {service} in {environment}. Do you want me to submit it?"
    )
    return confirmation_question, {
        "question": confirmation_question,
        "planning_mode": "agent_v2_incident_triage",
        "confirmation_kind": "ticket_submission",
        "missing_fields": ["submission_confirmation"],
        "follow_up_questions": [
            f"Confirm whether to submit ticket draft {ticket_id}."
        ],
        "clarification_summary": confirmation_question,
        "ticket_id": ticket_id,
        "service": service,
        "environment": environment,
    }


def _select_evidence_filename(service_record: dict, symptom: str) -> str | None:
    runbook_doc_ids = service_record.get("runbook_doc_ids")
    if not isinstance(runbook_doc_ids, list) or not runbook_doc_ids:
        return None

    lowered_symptom = symptom.lower()
    preferred_keywords = [lowered_symptom]
    if lowered_symptom == "timeout":
        preferred_keywords.extend(["runbook", "incident", "payment"])

    for keyword in preferred_keywords:
        for candidate in runbook_doc_ids:
            if isinstance(candidate, str) and keyword in candidate.lower():
                return candidate

    first_candidate = runbook_doc_ids[0]
    return first_candidate if isinstance(first_candidate, str) and first_candidate.strip() else None


def _run_incident_triage_workflow(state: AgentState, triage_context: dict[str, str]) -> dict:
    question = state["question"]
    service = triage_context["service"]
    environment = triage_context["environment"]
    severity = triage_context["severity"]
    symptom = triage_context["symptom"]
    tool_chain: list[dict] = []

    try:
        status_step, status_execution = _execute_single_step(
            state=state,
            step_index=1,
            question=question,
            tool_name="system_status",
            action="query",
            target=service,
            arguments={"environment": environment, "issue_type": symptom},
            planning_mode="agent_v2_incident_triage",
        )
        tool_chain.append(status_step)
        status_output = status_execution.model_dump().get("output", {})
        service_record = status_output.get("service_record", {})
        health = str(status_output.get("health") or status_output.get("status") or "").lower()
        if health in {"healthy", "ok", "nominal"}:
            return {
                "tool_chain": tool_chain,
                "answer": _build_incident_triage_summary(
                    service=service,
                    environment=environment,
                    symptom=symptom,
                    status_output=status_output,
                    search_output=None,
                    draft_output=None,
                ),
                "answer_source": "local_incident_triage",
                "workflow_status": "completed",
                "terminal_reason_override": "no_incident_detected",
                "failure_stage": None,
                "retry_state": "not_applicable",
                "retry_count": 0,
            }

        evidence_filename = _select_evidence_filename(service_record, symptom)
        search_step, search_execution = _execute_single_step(
            state=state,
            step_index=2,
            question=question,
            tool_name="document_search",
            action="query",
            target=symptom,
            arguments={
                "max_results": "3",
                **({"filename": evidence_filename} if evidence_filename else {}),
            },
            planning_mode="agent_v2_incident_triage",
        )
        tool_chain.append(search_step)
        search_output = search_execution.model_dump().get("output", {})

        external_search_step, external_search_execution = _execute_single_step(
            state=state,
            step_index=3,
            question=question,
            tool_name="document_search",
            action="query",
            target=_build_external_evidence_query(
                service=service,
                environment=environment,
                symptom=symptom,
                status_output=status_output,
            ),
            arguments={
                "max_results": "3",
                "search_mode": "qdrant",
                "source_prefixes": "customer_support_tickets_,it_support_v2_,bugsrepo_structured_",
            },
            planning_mode="agent_v2_incident_triage",
        )
        tool_chain.append(external_search_step)
        external_search_output = external_search_execution.model_dump().get("output", {})

        status_summary = status_output.get("summary") or f"{service} is degraded in {environment}."
        draft_step, draft_execution = _execute_single_step(
            state=state,
            step_index=4,
            question=question,
            tool_name="ticketing",
            action="draft",
            target=service,
            arguments={
                "severity": severity,
                "environment": environment,
                "supporting_summary": (
                    f"{status_summary} Observed symptom: {symptom}. "
                    f"External evidence: {external_search_output.get('matched_documents', '')}."
                ).strip(),
            },
            planning_mode="agent_v2_incident_triage",
        )
        tool_chain.append(draft_step)
        draft_output = draft_execution.model_dump().get("output", {})

        return {
            "tool_chain": tool_chain,
            "answer": _build_incident_triage_summary(
                service=service,
                environment=environment,
                symptom=symptom,
                status_output=status_output,
                search_output={
                    **search_output,
                    "matched_documents": ", ".join(
                        item
                        for item in [
                            str(search_output.get("matched_documents") or "").strip(),
                            str(external_search_output.get("matched_documents") or "").strip(),
                        ]
                        if item
                    ),
                },
                draft_output=draft_output,
            ),
            "answer_source": "local_incident_triage",
            "workflow_status": "clarification_required",
            "terminal_reason_override": None,
            "clarification_question": _build_ticket_submission_confirmation(
                service=service,
                environment=environment,
                draft_output=draft_output,
            )[0],
            "clarification_plan": _build_ticket_submission_confirmation(
                service=service,
                environment=environment,
                draft_output=draft_output,
            )[1],
            "failure_stage": None,
            "retry_state": "not_applicable",
            "retry_count": 0,
        }
    except Exception as exc:
        return {
            "tool_chain": tool_chain,
            "workflow_status": "failed",
            "terminal_reason_override": None,
            "failure_stage": "tool_execution",
            "retry_state": "retry_exhausted",
            "retry_count": 1,
            "error": str(exc),
        }


def tool_exec_node(state: AgentState) -> dict:
    """Plan and execute a tool request using the existing tool service."""
    question = state["question"]
    incident_triage_context = _extract_incident_triage_context(question)
    if incident_triage_context is not None:
        return _run_incident_triage_workflow(state, incident_triage_context)

    started_at = build_utc_timestamp()
    tool_plan = plan_tool_request(question)
    fault_rule = _get_matching_fault_rule(state, tool_plan.tool_name, tool_plan.action)
    if fault_rule is not None:
        failure_message = str(fault_rule.get("message") or "debug injected tool execution failure")
        return {
            "tool_chain": [
                {
                    "step_id": "step_1",
                    "step_index": 1,
                    "step_status": "failed",
                    "attempt_count": 1,
                    "retried": False,
                    "started_at": started_at,
                    "completed_at": build_utc_timestamp(),
                    "question": question,
                    "tool_plan": tool_plan.model_dump(),
                    "tool_execution": None,
                    "failure_message": failure_message,
                }
            ],
            "workflow_status": "failed",
            "terminal_reason_override": None,
            "failure_stage": "tool_execution",
            "retry_state": "retry_exhausted",
            "retry_count": 1,
            "error": failure_message,
        }
    execution_request = ToolExecutionRequest(
        tool_name=tool_plan.tool_name,
        action=tool_plan.action,
        target=tool_plan.target,
        arguments=tool_plan.arguments,
    )
    try:
        tool_execution = execute_tool_request(execution_request)
    except Exception as exc:
        failure_message = str(exc)
        return {
            "tool_chain": [
                {
                    "step_id": "step_1",
                    "step_index": 1,
                    "step_status": "failed",
                    "attempt_count": 1,
                    "retried": False,
                    "started_at": started_at,
                    "completed_at": build_utc_timestamp(),
                    "question": question,
                    "tool_plan": tool_plan.model_dump(),
                    "tool_execution": None,
                    "failure_message": failure_message,
                }
            ],
            "workflow_status": "failed",
            "terminal_reason_override": None,
            "failure_stage": "tool_execution",
            "retry_state": "retry_exhausted",
            "retry_count": 1,
            "error": failure_message,
        }
    step_record = {
        "step_id": "step_1",
        "step_index": 1,
        "step_status": tool_execution.execution_status,
        "attempt_count": 1,
        "retried": False,
        "started_at": started_at,
        "completed_at": tool_execution.executed_at,
        "question": question,
        "tool_plan": tool_plan.model_dump(),
        "tool_execution": tool_execution.model_dump(),
        "failure_message": None,
    }

    return {
        "tool_chain": [step_record],
        "answer": tool_execution.result_summary,
        "answer_source": "tool_result",
        "workflow_status": "completed",
        "terminal_reason_override": None,
        "failure_stage": None,
        "retry_state": "not_applicable",
        "retry_count": 0,
    }
