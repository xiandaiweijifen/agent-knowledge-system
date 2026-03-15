import json
import re
import uuid
from pathlib import Path

from app.schemas.query import (
    AgentWorkflowResponse,
    AgentWorkflowRunListResponse,
    AgentWorkflowRunSummary,
    WorkflowTraceEvent,
)
from app.schemas.tools import ToolExecutionRequest
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.agent.clarification_service import (
    plan_clarification,
    plan_search_miss_clarification,
    plan_search_summary_miss_clarification,
)
from app.services.agent.query_service import run_query
from app.services.agent.router_service import route_request
from app.services.agent.tool_service import execute_tool_request, plan_tool_request

WORKFLOW_RUN_DATA_DIR = Path("../data/tool_state")
WORKFLOW_RUN_DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKFLOW_RUN_STORE_PATH = WORKFLOW_RUN_DATA_DIR / "workflow_runs.json"

SEARCH_AND_TICKET_PATTERN = re.compile(
    r"(?P<search>^(?:search|find|lookup).+?)\s+and\s+(?P<ticket>(?:create|open).+\bticket\b.+)$",
    re.IGNORECASE,
)
SEARCH_AND_SUMMARIZE_PATTERN = re.compile(
    r"(?P<search>^(?:search|find|lookup).+?)\s+and\s+(?P<summarize>summari[sz]e.+)$",
    re.IGNORECASE,
)


def _load_workflow_runs() -> list[dict]:
    if not WORKFLOW_RUN_STORE_PATH.exists():
        return []
    raw_content = WORKFLOW_RUN_STORE_PATH.read_text(encoding="utf-8").strip()
    if not raw_content:
        return []
    try:
        loaded = json.loads(raw_content)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return loaded


def _save_workflow_runs(runs: list[dict]) -> None:
    WORKFLOW_RUN_STORE_PATH.write_text(
        json.dumps(runs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _persist_workflow_response(
    response: AgentWorkflowResponse,
    resumed_from_question: str | None = None,
    source_run_id: str | None = None,
) -> AgentWorkflowResponse:
    response.run_id = uuid.uuid4().hex
    response.resumed_from_question = resumed_from_question
    response.source_run_id = source_run_id
    runs = _load_workflow_runs()
    runs.append(response.model_dump())
    _save_workflow_runs(runs)
    return response


def get_persisted_workflow_run(run_id: str) -> AgentWorkflowResponse:
    normalized_run_id = run_id.strip()
    if not normalized_run_id:
        raise ValueError("run_id_must_not_be_empty")

    for run in reversed(_load_workflow_runs()):
        if run.get("run_id") == normalized_run_id:
            return AgentWorkflowResponse.model_validate(run)

    raise FileNotFoundError(run_id)


def list_persisted_workflow_runs(limit: int = 20) -> AgentWorkflowRunListResponse:
    if limit <= 0:
        raise ValueError("limit_must_be_positive")

    persisted_runs = [
        AgentWorkflowResponse.model_validate(run)
        for run in reversed(_load_workflow_runs())
    ][:limit]

    return AgentWorkflowRunListResponse(
        runs=[
            AgentWorkflowRunSummary(
                run_id=run.run_id or "",
                question=run.question,
                resumed_from_question=run.resumed_from_question,
                source_run_id=run.source_run_id,
                workflow_status=run.workflow_status,
                route_type=run.route.route_type,
                route_reason=run.route.route_reason,
                filename=run.filename,
                answered_at=run.answered_at,
            )
            for run in persisted_runs
            if run.run_id
        ]
    )


def _match_search_then_ticket_workflow(question: str) -> tuple[str, str] | None:
    match = SEARCH_AND_TICKET_PATTERN.match(question.strip())
    if not match:
        return None

    return match.group("search").strip(), match.group("ticket").strip()


def _match_search_then_summarize_workflow(question: str) -> tuple[str, str] | None:
    match = SEARCH_AND_SUMMARIZE_PATTERN.match(question.strip())
    if not match:
        return None

    return match.group("search").strip(), match.group("summarize").strip()


def _build_search_context_arguments(tool_output: dict[str, str]) -> dict[str, str]:
    arguments: dict[str, str] = {}

    query = tool_output.get("query", "").strip()
    matched_documents = tool_output.get("matched_documents", "").strip()
    snippets = tool_output.get("snippets", "").strip()
    matched_count = tool_output.get("matched_count", "").strip()

    if query:
        arguments["supporting_query"] = query
    if matched_documents:
        arguments["supporting_documents"] = matched_documents
    if snippets:
        arguments["supporting_snippets"] = snippets
    if matched_count:
        arguments["supporting_match_count"] = matched_count

    return arguments


def _split_search_snippets(snippets: str) -> list[tuple[str | None, str]]:
    parsed_snippets: list[tuple[str | None, str]] = []
    for raw_snippet in snippets.split(" | "):
        snippet = raw_snippet.strip()
        if not snippet:
            continue
        if ": " in snippet:
            source, content = snippet.split(": ", maxsplit=1)
            parsed_snippets.append((source.strip(), content.strip()))
        else:
            parsed_snippets.append((None, snippet))
    return parsed_snippets


def _ensure_summary_sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def _build_search_summary(tool_output: dict[str, str]) -> str:
    query = tool_output.get("query", "").strip()
    matched_count = tool_output.get("matched_count", "0").strip()
    returned_count = tool_output.get("returned_count", matched_count).strip()
    matched_documents = tool_output.get("matched_documents", "").strip()
    snippets = tool_output.get("snippets", "").strip()
    top_match_document = tool_output.get("top_match_document", "").strip()
    filename_filter = tool_output.get("filename_filter", "").strip()
    max_results = tool_output.get("max_results", "").strip()
    parsed_snippets = _split_search_snippets(snippets)

    summary_parts: list[str] = []

    if query:
        if filename_filter:
            summary_parts.append(
                f"I searched '{filename_filter}' for '{query}' and found {matched_count} matching result(s)."
            )
        else:
            summary_parts.append(
                f"I found {matched_count} matching document(s) for '{query}' and returned {returned_count} result(s)."
            )

    if max_results and matched_count and returned_count and matched_count != returned_count:
        summary_parts.append(
            f"Showing the top {returned_count} result(s) out of {matched_count} total matches."
        )

    if top_match_document:
        summary_parts.append(f"The strongest supporting document is {top_match_document}.")

    if matched_documents:
        document_list = [item.strip() for item in matched_documents.split(",") if item.strip()]
        if len(document_list) > 1:
            summary_parts.append(f"Returned documents: {', '.join(document_list)}.")

    if parsed_snippets:
        first_source, first_snippet = parsed_snippets[0]
        first_snippet = _ensure_summary_sentence(first_snippet)
        if first_source:
            summary_parts.append(f"Key evidence from {first_source}: {first_snippet}")
        else:
            summary_parts.append(f"Key evidence: {first_snippet}")

    if len(parsed_snippets) > 1:
        second_source, second_snippet = parsed_snippets[1]
        second_snippet = _ensure_summary_sentence(second_snippet)
        if second_source and second_source != top_match_document:
            summary_parts.append(f"Additional support from {second_source}: {second_snippet}")

    return " ".join(summary_parts).strip()


def _extract_summary_step_context(summarize_question: str) -> dict[str, str]:
    summary_plan = plan_tool_request(
        re.sub(r"^summari[sz]e\s+", "Search ", summarize_question.strip(), flags=re.IGNORECASE)
    )
    if summary_plan.tool_name != "document_search":
        return {}

    context: dict[str, str] = {}
    if "max_results" in summary_plan.arguments:
        context["max_results"] = summary_plan.arguments["max_results"]
    return context


def _build_workflow_step_record(
    *,
    step_index: int,
    step_question: str,
    tool_plan: dict,
    tool_execution: dict,
    started_at: str,
    completed_at: str,
) -> dict:
    return {
        "step_id": f"step_{step_index}",
        "step_index": step_index,
        "step_status": tool_execution.get("execution_status", "completed"),
        "started_at": started_at,
        "completed_at": completed_at,
        "question": step_question,
        "tool_plan": tool_plan,
        "tool_execution": tool_execution,
    }


def _normalize_confirmation(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "confirmed", "continue"}


def _extract_resume_ticket_overrides(clarification_context: dict[str, str]) -> dict[str, str]:
    overrides: dict[str, str] = {}

    for key in ("environment", "severity", "status", "ticket_id"):
        value = clarification_context.get(key, "").strip()
        if value:
            overrides[key] = value

    return overrides


def _resume_search_question(
    search_question: str,
    clarification_context: dict[str, str],
) -> str:
    query_override = clarification_context.get("search_query_refinement", "").strip()
    filename_override = (
        clarification_context.get("document_scope", "").strip()
        or clarification_context.get("filename", "").strip()
    )

    search_plan = plan_tool_request(search_question)
    resolved_query = query_override or search_plan.target

    if filename_override:
        return f"Search {filename_override} for {resolved_query}"

    if search_plan.arguments.get("filename"):
        return f"Search {search_plan.arguments['filename']} for {resolved_query}"

    return f"Search docs for {resolved_query}"


def _resume_ticket_question(
    ticket_question: str,
    clarification_context: dict[str, str],
) -> str:
    updated_question = ticket_question.strip()
    environment = clarification_context.get("environment", "").strip().lower()

    if environment and environment in {"production", "staging"}:
        if environment not in updated_question.lower():
            updated_question = f"{updated_question} in {environment}"

    return updated_question


def _resume_generic_question(
    original_question: str,
    clarification_context: dict[str, str],
) -> str:
    tokens: list[str] = []
    for key, value in clarification_context.items():
        if not value.strip():
            continue
        label = key.replace("_", " ")
        tokens.append(f"{label}: {value.strip()}")

    if not tokens:
        return original_question

    return f"{original_question} {' '.join(tokens)}"


def _resolve_resume_source(
    original_question: str | None,
    run_id: str | None,
) -> tuple[str, str | None, str | None]:
    normalized_question = (original_question or "").strip()
    normalized_run_id = (run_id or "").strip()

    if normalized_question:
        return normalized_question, None, None

    if not normalized_run_id:
        raise ValueError("original_question_or_run_id_required")

    persisted_run = get_persisted_workflow_run(normalized_run_id)
    return persisted_run.question, persisted_run.filename, persisted_run.run_id


def resume_agent_request(
    original_question: str | None,
    clarification_context: dict[str, str],
    run_id: str | None = None,
    filename: str | None = None,
    top_k: int = 3,
) -> AgentWorkflowResponse:
    if not clarification_context:
        raise ValueError("clarification_context_required")

    source_question, source_filename, source_run_id = _resolve_resume_source(original_question, run_id)
    resumed_question = source_question.strip()

    search_then_ticket = _match_search_then_ticket_workflow(resumed_question)
    search_then_summarize = _match_search_then_summarize_workflow(resumed_question)

    if search_then_ticket is not None:
        search_question, ticket_question = search_then_ticket
        resumed_search = _resume_search_question(search_question, clarification_context)
        resumed_ticket = _resume_ticket_question(ticket_question, clarification_context)
        execution_confirmed = _normalize_confirmation(
            clarification_context.get("execution_confirmation", "")
        )

        if not clarification_context.get("search_query_refinement", "").strip() and not execution_confirmed:
            raise ValueError("search_query_refinement_or_execution_confirmation_required")

        resumed_question = f"{resumed_search} and {resumed_ticket}"

    elif search_then_summarize is not None:
        search_question, summarize_question = search_then_summarize
        resumed_search = _resume_search_question(search_question, clarification_context)
        resumed_question = f"{resumed_search} and {summarize_question}"

    else:
        resumed_question = _resume_generic_question(original_question, clarification_context)

    response = orchestrate_agent_request(
        question=resumed_question,
        filename=filename if filename is not None else source_filename,
        top_k=top_k,
        resume_context=clarification_context,
        persist_run=False,
    )
    response.workflow_trace.insert(
        0,
        WorkflowTraceEvent(
            stage="workflow_resume",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=f"Resumed workflow from '{source_question}' using clarification context.",
        ),
    )
    response.question = resumed_question
    return _persist_workflow_response(
        response=response,
        resumed_from_question=source_question,
        source_run_id=source_run_id,
    )


def orchestrate_agent_request(
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    resume_context: dict[str, str] | None = None,
    persist_run: bool = True,
) -> AgentWorkflowResponse:
    """Route and execute the next workflow step for an agent request."""
    route = route_request(question=question, filename=filename)
    workflow_trace = [
        WorkflowTraceEvent(
            stage="routing",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=f"Request routed to {route.route_type}.",
        )
    ]

    if route.route_type == "knowledge_retrieval":
        if not filename:
            raise ValueError("filename_required_for_knowledge_route")

        query_response = run_query(
            filename=filename,
            question=question,
            top_k=top_k,
        )
        workflow_trace.extend(
            [
                WorkflowTraceEvent(
                    stage="retrieval",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=(
                        f"Retrieved {len(query_response.retrieval.matches)} supporting chunks "
                        f"from {query_response.filename}."
                    ),
                ),
                WorkflowTraceEvent(
                    stage="answer_generation",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=f"Answer generated via {query_response.chat_provider}.",
                ),
            ]
        )
        response = AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            route=route,
            workflow_trace=workflow_trace,
            filename=query_response.filename,
            answer=query_response.answer,
            answer_source=query_response.answer_source,
            model=query_response.model,
            answered_at=query_response.answered_at,
            answer_latency_ms=query_response.answer_latency_ms,
            chat_provider=query_response.chat_provider,
            chat_model=query_response.chat_model,
            retrieval=query_response.retrieval,
        )
        return _persist_workflow_response(response) if persist_run else response

    if route.route_type == "tool_execution":
        chained_steps: list[dict] = []
        search_then_ticket = _match_search_then_ticket_workflow(question)
        search_then_summarize = _match_search_then_summarize_workflow(question)
        resume_context = resume_context or {}

        if search_then_ticket is not None:
            search_question, ticket_question = search_then_ticket
            prior_search_context: dict[str, str] = {}
            ticket_resume_overrides = _extract_resume_ticket_overrides(resume_context)
            execution_confirmed = _normalize_confirmation(
                resume_context.get("execution_confirmation", "")
            )

            for step_index, step_question in enumerate((search_question, ticket_question), start=1):
                step_started_at = build_utc_timestamp()
                tool_plan = plan_tool_request(step_question)
                if (
                    step_index == 2
                    and tool_plan.tool_name == "ticketing"
                    and tool_plan.action == "create"
                    and prior_search_context
                ):
                    tool_plan.arguments = {
                        **prior_search_context,
                        **tool_plan.arguments,
                    }
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="tool_context",
                            status="completed",
                            timestamp=build_utc_timestamp(),
                            detail=(
                                "Step 2 inherited supporting search context from step 1 "
                                "before ticket creation."
                            ),
                        )
                    )
                if step_index == 2 and ticket_resume_overrides:
                    tool_plan.arguments = {
                        **tool_plan.arguments,
                        **ticket_resume_overrides,
                    }
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="resume_context",
                            status="completed",
                            timestamp=build_utc_timestamp(),
                            detail="Applied structured clarification fields to ticket execution.",
                        )
                    )
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="tool_planning",
                        status="completed",
                        timestamp=build_utc_timestamp(),
                        detail=(
                            f"Step {step_index}: planned {tool_plan.tool_name}:{tool_plan.action} "
                            f"for {tool_plan.target}."
                        ),
                    )
                )
                tool_response = execute_tool_request(
                    ToolExecutionRequest(
                        tool_name=tool_plan.tool_name,
                        action=tool_plan.action,
                        target=tool_plan.target,
                        arguments=tool_plan.arguments,
                    )
                )
                step_completed_at = build_utc_timestamp()
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="tool_execution",
                        status="completed",
                        timestamp=step_completed_at,
                        detail=(
                            f"Step {step_index}: executed {tool_response.execution_mode} tool "
                            f"{tool_response.tool_name}:{tool_response.action} "
                            f"with status {tool_response.execution_status}."
                        ),
                    )
                )
                chained_steps.append(
                    _build_workflow_step_record(
                        step_index=step_index,
                        step_question=step_question,
                        tool_plan=tool_plan.model_dump(),
                        tool_execution=tool_response.model_dump(),
                        started_at=step_started_at,
                        completed_at=step_completed_at,
                    )
                )

                if (
                    step_index == 1
                    and tool_response.tool_name == "document_search"
                    and tool_response.output.get("matched_count") == "0"
                ):
                    if execution_confirmed:
                        workflow_trace.append(
                            WorkflowTraceEvent(
                                stage="resume_context",
                                status="completed",
                                timestamp=build_utc_timestamp(),
                                detail=(
                                    "Search returned no supporting documents, but execution continued "
                                    "because the clarified workflow explicitly confirmed proceeding."
                                ),
                            )
                        )
                        prior_search_context = {}
                        continue
                    clarification_plan = plan_search_miss_clarification(
                        search_query=tool_plan.target,
                        next_action_question=ticket_question,
                    )
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="clarification_planning",
                            status="completed",
                            timestamp=build_utc_timestamp(),
                            detail=(
                                "Search produced no supporting documents, so the workflow "
                                "stopped before ticket creation and requested clarification."
                            ),
                        )
                    )
                    response = AgentWorkflowResponse(
                        question=question,
                        workflow_status="clarification_required",
                        route=route,
                        workflow_trace=workflow_trace,
                        filename=filename,
                        clarification_message=(
                            "No supporting documents matched the search step, so the system "
                            "needs clarification before creating a ticket."
                        ),
                        clarification_plan=clarification_plan.model_dump(),
                        tool_plan=tool_plan.model_dump(),
                        tool_execution=tool_response.model_dump(),
                        step_count=len(chained_steps),
                        tool_chain=chained_steps,
                    )
                    return _persist_workflow_response(response) if persist_run else response

                if step_index == 1 and tool_response.tool_name == "document_search":
                    prior_search_context = _build_search_context_arguments(tool_response.output)

            final_step = chained_steps[-1]
            response = AgentWorkflowResponse(
                question=question,
                workflow_status="completed",
                step_count=len(chained_steps),
                route=route,
                workflow_trace=workflow_trace,
                filename=filename,
                tool_plan=final_step["tool_plan"],
                tool_execution=final_step["tool_execution"],
                tool_chain=chained_steps,
            )
            return _persist_workflow_response(response) if persist_run else response

        if search_then_summarize is not None:
            search_question, summarize_question = search_then_summarize
            step_started_at = build_utc_timestamp()
            tool_plan = plan_tool_request(search_question)
            summary_context = _extract_summary_step_context(summarize_question)
            if summary_context:
                tool_plan.arguments = {
                    **tool_plan.arguments,
                    **summary_context,
                }
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="tool_planning",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=(
                        f"Planned {tool_plan.tool_name}:{tool_plan.action} for "
                        f"{tool_plan.target}."
                    ),
                )
            )
            tool_response = execute_tool_request(
                ToolExecutionRequest(
                    tool_name=tool_plan.tool_name,
                    action=tool_plan.action,
                    target=tool_plan.target,
                    arguments=tool_plan.arguments,
                )
            )
            step_completed_at = build_utc_timestamp()
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="tool_execution",
                    status="completed",
                    timestamp=step_completed_at,
                    detail=(
                        f"Executed {tool_response.execution_mode} tool "
                        f"{tool_response.tool_name}:{tool_response.action} "
                        f"with status {tool_response.execution_status}."
                    ),
                )
            )
            chained_steps.append(
                _build_workflow_step_record(
                    step_index=1,
                    step_question=search_question,
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response.model_dump(),
                    started_at=step_started_at,
                    completed_at=step_completed_at,
                )
            )

            if tool_response.output.get("matched_count") == "0":
                clarification_plan = plan_search_summary_miss_clarification(tool_plan.target)
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="clarification_planning",
                        status="completed",
                        timestamp=build_utc_timestamp(),
                        detail=(
                            "Search produced no supporting documents, so the workflow "
                            "stopped before summary generation and requested clarification."
                        ),
                    )
                )
                response = AgentWorkflowResponse(
                    question=question,
                    workflow_status="clarification_required",
                    route=route,
                    workflow_trace=workflow_trace,
                    filename=filename,
                    clarification_message=(
                        "No supporting documents matched the search step, so the system "
                        "needs clarification before generating a summary."
                    ),
                    clarification_plan=clarification_plan.model_dump(),
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response.model_dump(),
                    step_count=len(chained_steps),
                    tool_chain=chained_steps,
                )
                return _persist_workflow_response(response) if persist_run else response

            summary_answer = _build_search_summary(tool_response.output)
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="search_summary",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=(
                        f"Generated a local summary for search results in response to "
                        f"'{summarize_question}'."
                    ),
                )
            )
            answered_at = build_utc_timestamp()
            response = AgentWorkflowResponse(
                question=question,
                workflow_status="completed",
                route=route,
                workflow_trace=workflow_trace,
                filename=filename,
                answer=summary_answer,
                answer_source="local_search_summary",
                model="local-heuristic-summary",
                answered_at=answered_at,
                answer_latency_ms=0.0,
                chat_provider="local",
                chat_model="local-heuristic-summary",
                tool_plan=tool_plan.model_dump(),
                tool_execution=tool_response.model_dump(),
                step_count=len(chained_steps),
                tool_chain=chained_steps,
            )
            return _persist_workflow_response(response) if persist_run else response

        step_started_at = build_utc_timestamp()
        tool_plan = plan_tool_request(question)
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="tool_planning",
                status="completed",
                timestamp=build_utc_timestamp(),
                detail=(
                    f"Planned {tool_plan.tool_name}:{tool_plan.action} for "
                    f"{tool_plan.target}."
                ),
            )
        )
        tool_response = execute_tool_request(
            ToolExecutionRequest(
                tool_name=tool_plan.tool_name,
                action=tool_plan.action,
                target=tool_plan.target,
                arguments=tool_plan.arguments,
            )
        )
        step_completed_at = build_utc_timestamp()
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="tool_execution",
                status="completed",
                timestamp=step_completed_at,
                detail=(
                    f"Executed {tool_response.execution_mode} tool "
                    f"{tool_response.tool_name}:{tool_response.action} "
                    f"with status {tool_response.execution_status}."
                ),
            )
        )
        response = AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            step_count=1,
            route=route,
            workflow_trace=workflow_trace,
            filename=filename,
            tool_plan=tool_plan.model_dump(),
            tool_execution=tool_response.model_dump(),
            tool_chain=[
                _build_workflow_step_record(
                    step_index=1,
                    step_question=question,
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response.model_dump(),
                    started_at=step_started_at,
                    completed_at=step_completed_at,
                )
            ],
        )
        return _persist_workflow_response(response) if persist_run else response

    clarification_plan = plan_clarification(question)
    workflow_trace.append(
        WorkflowTraceEvent(
            stage="clarification_planning",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=(
                f"Clarification requested for fields: "
                f"{', '.join(clarification_plan.missing_fields)}."
            ),
        )
    )
    response = AgentWorkflowResponse(
        question=question,
        workflow_status="clarification_required",
        step_count=0,
        route=route,
        workflow_trace=workflow_trace,
        filename=filename,
        clarification_message=clarification_plan.clarification_summary,
        clarification_plan=clarification_plan.model_dump(),
        tool_chain=[],
    )
    return _persist_workflow_response(response) if persist_run else response
