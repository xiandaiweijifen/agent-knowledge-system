"""Tool execution node — runs tool actions requested by the router."""

import re

from app.schemas.tools import ToolExecutionRequest
from app.services.agent.tool_service import execute_tool_request, plan_tool_request
from app.services.agent_v2.skills.incident_triage import (
    build_incident_triage_summary,
    run_collect_incident_evidence_skill,
    run_prepare_incident_ticket_skill,
    run_review_service_health_skill,
)
from app.services.agent_v2.skills.service_runtime_review import (
    build_runtime_review_summary,
    run_collect_dependency_context_skill,
    run_collect_runtime_guidance_skill,
)
from app.services.agent_v2.state import AgentState
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.llm.skill_planner_service import generate_llm_skill_decision


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


def _build_incident_triage_context(question: str) -> dict[str, str] | None:
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


def _build_service_runtime_review_context(question: str) -> dict[str, str] | None:
    service_match = SERVICE_PATTERN.search(question)
    if service_match is None:
        return None

    environment_match = ENVIRONMENT_PATTERN.search(question)
    symptom_match = SYMPTOM_PATTERN.search(question)
    return {
        "service": service_match.group(1),
        "environment": _normalize_environment(environment_match.group(1) if environment_match else None),
        "symptom": (symptom_match.group(1).lower() if symptom_match else "health"),
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


def _get_reused_step_output(reuse_chain: list[dict], step_index: int) -> dict:
    """Extract tool execution output from a pre-completed step by 1-based step_index."""
    for step in reuse_chain:
        if not isinstance(step, dict):
            continue
        if step.get("step_index") == step_index:
            return (step.get("tool_execution") or {}).get("output") or {}
    return {}


def _run_incident_triage_workflow(
    state: AgentState,
    triage_context: dict[str, str],
    *,
    reuse_chain: list[dict] | None = None,
    skip_to_step: int = 0,
) -> dict:
    question = state["question"]
    service = triage_context["service"]
    environment = triage_context["environment"]
    severity = triage_context["severity"]
    symptom = triage_context["symptom"]
    reuse_chain = reuse_chain or []
    # Start tool_chain with any pre-completed steps from a prior run.
    tool_chain: list[dict] = list(reuse_chain)

    try:
        if skip_to_step <= 0:
            status_steps, status_output = run_review_service_health_skill(
                state=state,
                question=question,
                service=service,
                environment=environment,
                symptom=symptom,
                planning_mode="agent_v2_incident_triage",
                execute_step=_execute_single_step,
            )
            tool_chain.extend(status_steps)
        else:
            status_output = _get_reused_step_output(reuse_chain, step_index=1)

        health = str(status_output.get("health") or status_output.get("status") or "").lower()
        if health in {"healthy", "ok", "nominal"}:
            return {
                "tool_chain": tool_chain,
                "answer": build_incident_triage_summary(
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

        if skip_to_step <= 1:
            evidence_steps, search_output, external_search_output = run_collect_incident_evidence_skill(
                state=state,
                question=question,
                service=service,
                environment=environment,
                symptom=symptom,
                status_output=status_output,
                execute_step=_execute_single_step,
            )
            tool_chain.extend(evidence_steps)
        else:
            search_output = _get_reused_step_output(reuse_chain, step_index=2)
            external_search_output = _get_reused_step_output(reuse_chain, step_index=3)

        ticket_steps, draft_output, clarification_question, clarification_plan = run_prepare_incident_ticket_skill(
            state=state,
            question=question,
            service=service,
            environment=environment,
            severity=severity,
            symptom=symptom,
            status_output=status_output,
            external_search_output=external_search_output,
            execute_step=_execute_single_step,
        )
        tool_chain.extend(ticket_steps)

        return {
            "tool_chain": tool_chain,
            "answer": build_incident_triage_summary(
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
            "clarification_question": clarification_question,
            "clarification_plan": clarification_plan,
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


def _run_service_runtime_review_workflow(
    state: AgentState,
    review_context: dict[str, str],
    *,
    reuse_chain: list[dict] | None = None,
    skip_to_step: int = 0,
) -> dict:
    question = state["question"]
    service = review_context["service"]
    environment = review_context["environment"]
    symptom = review_context["symptom"]
    reuse_chain = reuse_chain or []
    tool_chain: list[dict] = list(reuse_chain)

    try:
        if skip_to_step <= 0:
            status_steps, status_output = run_review_service_health_skill(
                state=state,
                question=question,
                service=service,
                environment=environment,
                symptom=symptom,
                planning_mode="agent_v2_service_runtime_review",
                execute_step=_execute_single_step,
            )
            tool_chain.extend(status_steps)
        else:
            status_output = _get_reused_step_output(reuse_chain, step_index=1)

        if skip_to_step <= 1:
            dependency_steps, dependency_output = run_collect_dependency_context_skill(
                state=state,
                question=question,
                service=service,
                environment=environment,
                status_output=status_output,
                execute_step=_execute_single_step,
            )
            tool_chain.extend(dependency_steps)
        else:
            dependency_output = _get_reused_step_output(reuse_chain, step_index=2)

        if skip_to_step <= 2:
            guidance_steps, guidance_output = run_collect_runtime_guidance_skill(
                state=state,
                question=question,
                service=service,
                symptom=symptom,
                status_output=status_output,
                execute_step=_execute_single_step,
            )
            tool_chain.extend(guidance_steps)
        else:
            guidance_output = _get_reused_step_output(reuse_chain, step_index=3)

        return {
            "tool_chain": tool_chain,
            "answer": build_runtime_review_summary(
                service=service,
                environment=environment,
                symptom=symptom,
                status_output=status_output,
                dependency_output=dependency_output,
                guidance_output=guidance_output,
            ),
            "answer_source": "local_service_runtime_review",
            "workflow_status": "completed",
            "terminal_reason_override": "service_runtime_review_completed",
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
    resume_hints = state.get("resume_hints") or {}
    reuse_chain: list[dict] = resume_hints.get("reuse_tool_chain") or []
    skip_to_step: int = int(resume_hints.get("skip_to_step") or 0)

    question = state["question"]
    _skill_planning_mode, skill_payload = generate_llm_skill_decision(question)
    skill_id = (skill_payload or {}).get("skill_id")

    if skill_id == "incident_triage":
        triage_context = _build_incident_triage_context(question)
        if triage_context is not None:
            return _run_incident_triage_workflow(
                state, triage_context, reuse_chain=reuse_chain, skip_to_step=skip_to_step
            )

    if skill_id == "service_runtime_review":
        review_context = _build_service_runtime_review_context(question)
        if review_context is not None:
            return _run_service_runtime_review_workflow(
                state, review_context, reuse_chain=reuse_chain, skip_to_step=skip_to_step
            )

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
