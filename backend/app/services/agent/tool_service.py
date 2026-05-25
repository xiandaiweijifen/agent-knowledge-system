import re
import uuid

from app.schemas.tools import (
    InferredToolRequest,
    ToolArgumentSpec,
    ToolCatalogEntry,
    ToolCatalogResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolPlanResponse,
    ToolResultFieldSpec,
)
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.llm.tool_planner_service import generate_llm_tool_plan

# Importing from adapters triggers __init__.py which registers all adapters.
from app.services.agent.adapters.registry import get_adapter
from app.services.agent.adapters._shared import (
    ACTION_PATTERN,
    ENVIRONMENT_SEGMENT_PATTERN,
    GENERIC_SEARCH_PREFIX_PATTERN,
    RESULT_LIMIT_PATTERN,
    SEARCH_PREFIX_PATTERN,
    SERVICE_DEPENDENCIES_FOR_PATTERN,
    STATUS_PREFIX_PATTERN,
    SYSTEM_STATUS_FOR_PATTERN,
    _canonicalize_ticket_target,
    _clean_ticket_target,
    _extract_environment_argument,
    _extract_filename_argument,
    _extract_search_max_results_argument,
    _extract_ticket_id_argument,
    _extract_ticket_target_filter,
    _extract_ticket_update_arguments,
    _is_generic_ticket_target,
    _normalize_environment_value,
    _pop_ticket_target_argument,
)


SUPPORTED_TOOLS: dict[str, dict[str, object]] = {
    "ticketing": {
        "supported_actions": ["draft", "submit", "create", "update", "close", "query", "list"],
        "description": "Create, inspect, update, or close incident and ticket records for operational issues.",
        "execution_mode": "local_adapter",
        "primary_resource": "incident_ticket",
        "domain_entities": ["IncidentTicket", "ServiceRecord"],
        "confirmation_required_actions": ["submit", "update", "close"],
        "argument_schema": [
            {
                "name": "target",
                "value_type": "string",
                "required": True,
                "description": "Service or incident target for the ticket action.",
                "domain_entity": "ServiceRecord",
            },
            {
                "name": "severity",
                "value_type": "string",
                "required": False,
                "description": "Severity level for incident-style tickets.",
                "enum_values": ["high", "medium", "low", "unspecified"],
                "domain_entity": "IncidentTicket",
            },
            {
                "name": "environment",
                "value_type": "string",
                "required": False,
                "description": "Environment affected by the incident.",
                "enum_values": ["production", "staging", "development", "unspecified"],
                "domain_entity": "IncidentTicket",
            },
        ],
        "result_schema": [
            {
                "name": "ticket_record",
                "value_type": "object",
                "description": "Structured incident ticket record.",
                "domain_entity": "IncidentTicket",
            },
            {
                "name": "ticket_records",
                "value_type": "array",
                "description": "Structured incident ticket collection for list actions.",
                "domain_entity": "IncidentTicket",
            },
            {
                "name": "ticket_artifact_path",
                "value_type": "string",
                "description": "Local markdown artifact path for a created or updated ticket.",
                "domain_entity": "IncidentTicket",
            },
            {
                "name": "ticket_artifact_json_path",
                "value_type": "string",
                "description": "Local JSON artifact path for a created or updated ticket.",
                "domain_entity": "IncidentTicket",
            },
        ],
    },
    "system_status": {
        "supported_actions": ["query"],
        "description": "Inspect service or system health status through a status-style tool interface.",
        "execution_mode": "local_adapter",
        "primary_resource": "status_snapshot",
        "domain_entities": ["ServiceRecord", "StatusSnapshot"],
        "confirmation_required_actions": [],
        "argument_schema": [
            {
                "name": "target",
                "value_type": "string",
                "required": True,
                "description": "Service or system name to inspect.",
                "domain_entity": "ServiceRecord",
            },
            {
                "name": "environment",
                "value_type": "string",
                "required": False,
                "description": "Requested environment for the status check.",
                "enum_values": ["production", "staging", "development"],
                "domain_entity": "StatusSnapshot",
            },
            {
                "name": "scenario",
                "value_type": "string",
                "required": False,
                "description": "Optional mock scenario id used to select a specific status snapshot variant.",
                "domain_entity": "StatusSnapshot",
            },
        ],
        "result_schema": [
            {
                "name": "service_record",
                "value_type": "object",
                "description": "Structured service metadata for the requested target.",
                "domain_entity": "ServiceRecord",
            },
            {
                "name": "status_snapshot",
                "value_type": "object",
                "description": "Structured status snapshot for the service and environment.",
                "domain_entity": "StatusSnapshot",
            },
            {
                "name": "scenario_id",
                "value_type": "string",
                "description": "Resolved status scenario id used for the returned snapshot.",
                "domain_entity": "StatusSnapshot",
            },
        ],
    },
    "document_search": {
        "supported_actions": ["query"],
        "description": "Perform a tool-style document lookup outside the main retrieval answer flow.",
        "execution_mode": "local_adapter",
        "primary_resource": "knowledge_asset",
        "domain_entities": ["KnowledgeAsset"],
        "confirmation_required_actions": [],
        "argument_schema": [
            {
                "name": "target",
                "value_type": "string",
                "required": True,
                "description": "Free-text query to search across document content.",
            },
            {
                "name": "filename",
                "value_type": "string",
                "required": False,
                "description": "Optional filename filter for a single knowledge asset.",
                "domain_entity": "KnowledgeAsset",
            },
            {
                "name": "max_results",
                "value_type": "integer",
                "required": False,
                "description": "Optional hard limit on returned matches.",
            },
        ],
        "result_schema": [
            {
                "name": "knowledge_assets",
                "value_type": "array",
                "description": "Structured matched knowledge assets with snippets.",
                "domain_entity": "KnowledgeAsset",
            },
        ],
    },
    "service_dependencies": {
        "supported_actions": ["query"],
        "description": "Inspect downstream dependencies for a service using structured engineering dependency data.",
        "execution_mode": "local_adapter",
        "primary_resource": "service_dependency",
        "domain_entities": ["ServiceRecord", "ServiceDependency"],
        "confirmation_required_actions": [],
        "argument_schema": [
            {
                "name": "target",
                "value_type": "string",
                "required": True,
                "description": "Service name whose dependency map should be inspected.",
                "domain_entity": "ServiceRecord",
            },
            {
                "name": "environment",
                "value_type": "string",
                "required": False,
                "description": "Requested environment for dependency lookup.",
                "enum_values": ["production", "staging", "development"],
                "domain_entity": "ServiceRecord",
            },
            {
                "name": "failure_signal",
                "value_type": "string",
                "required": False,
                "description": "Optional failure signal used to prioritize the most relevant dependency.",
                "domain_entity": "ServiceDependency",
            },
            {
                "name": "dependency_name",
                "value_type": "string",
                "required": False,
                "description": "Optional downstream dependency name filter.",
                "domain_entity": "ServiceDependency",
            },
        ],
        "result_schema": [
            {
                "name": "service_record",
                "value_type": "object",
                "description": "Structured service metadata for the requested target.",
                "domain_entity": "ServiceRecord",
            },
            {
                "name": "dependencies",
                "value_type": "array",
                "description": "Structured downstream dependencies for the requested service.",
                "domain_entity": "ServiceDependency",
            },
        ],
    },
}


def execute_tool_request(request: ToolExecutionRequest) -> ToolExecutionResponse:
    """Dispatch a tool request to the registered adapter, or return a stub."""
    tool_name = request.tool_name.strip().lower()
    action = request.action.strip().lower()
    target = request.target.strip()

    if not tool_name or not action or not target:
        raise ValueError("tool_request_fields_must_not_be_empty")

    if tool_name not in SUPPORTED_TOOLS:
        raise ValueError("unsupported_tool_name")

    adapter = get_adapter(tool_name)
    if adapter is not None:
        return adapter(request)

    return ToolExecutionResponse(
        tool_name=tool_name,
        action=action,
        target=target,
        execution_status="stubbed",
        execution_mode="local_stub",
        result_summary=(
            f"Stubbed tool execution recorded for {tool_name}:{action} on {target}. "
            "No external side effects were triggered."
        ),
        trace_id=uuid.uuid4().hex,
        executed_at=build_utc_timestamp(),
        output={
            "target": target,
            "action": action,
            "note": "Replace this stub with a real tool adapter in the next iteration.",
        },
    )


def list_registered_tools() -> ToolCatalogResponse:
    """Return the currently registered tool catalog."""
    tools = [
        ToolCatalogEntry(
            tool_name=tool_name,
            supported_actions=list(tool_config["supported_actions"]),
            description=str(tool_config["description"]),
            execution_mode=str(tool_config["execution_mode"]),
            primary_resource=str(tool_config.get("primary_resource", "")),
            domain_entities=list(tool_config.get("domain_entities", [])),
            confirmation_required_actions=list(
                tool_config.get("confirmation_required_actions", [])
            ),
            argument_schema=[
                ToolArgumentSpec.model_validate(item)
                for item in tool_config.get("argument_schema", [])
            ],
            result_schema=[
                ToolResultFieldSpec.model_validate(item)
                for item in tool_config.get("result_schema", [])
            ],
        )
        for tool_name, tool_config in SUPPORTED_TOOLS.items()
    ]
    return ToolCatalogResponse(
        count=len(tools),
        tools=tools,
    )


def infer_tool_request(question: str) -> InferredToolRequest:
    """Infer a minimal tool request from a routed execution query."""
    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError("question_must_not_be_empty")

    lowered = normalized_question.lower()
    action_match = ACTION_PATTERN.search(lowered)
    action = action_match.group(1).lower() if action_match else "query"

    if "ticket" in lowered or "incident" in lowered:
        tool_name = "ticketing"
    elif any(token in lowered for token in ["dependency", "dependencies", "downstream dependency", "dependency map"]):
        tool_name = "service_dependencies"
        action = "query"
    elif any(token in lowered for token in ["status", "health", "config", "configuration"]):
        tool_name = "system_status"
        action = "query"
    else:
        tool_name = "document_search"
        action = "query"

    if tool_name == "ticketing":
        if action == "prepare":
            action = "draft"
        if action in {"set", "move"}:
            action = "update"
        if " for " in lowered:
            target = normalized_question.split(" for ", maxsplit=1)[1].strip()
        else:
            target = normalized_question
    elif tool_name == "system_status":
        target = STATUS_PREFIX_PATTERN.sub("", normalized_question).strip(" ?.!")
        target = SYSTEM_STATUS_FOR_PATTERN.sub("", target).strip(" ?.!")
        target = ENVIRONMENT_SEGMENT_PATTERN.sub("", target).strip(" ?.!")
        if not target:
            target = "agent-knowledge-system"
    elif tool_name == "service_dependencies":
        target = STATUS_PREFIX_PATTERN.sub("", normalized_question).strip(" ?.!")
        target = SERVICE_DEPENDENCIES_FOR_PATTERN.sub("", target).strip(" ?.!")
        target = re.sub(
            r"\b(?:dependency|dependencies|dependency\s+map|dependency\s+health)\b",
            "",
            target,
            flags=re.IGNORECASE,
        ).strip(" ?.!")
        target = ENVIRONMENT_SEGMENT_PATTERN.sub("", target).strip(" ?.!")
        if not target:
            target = "service"
    else:
        target = SEARCH_PREFIX_PATTERN.sub("", normalized_question).strip(" ?.!")
        target = GENERIC_SEARCH_PREFIX_PATTERN.sub("", target).strip(" ?.!")
        target = re.sub(r"^about\s+", "", target, flags=re.IGNORECASE).strip(" ?.!")
        if not target:
            target = normalized_question.strip(" ?.!") or "documents"

    return InferredToolRequest(
        tool_name=tool_name,
        action=action,
        target=target,
    )


def _build_tool_plan_response(
    *,
    question: str,
    inferred_request: InferredToolRequest,
    arguments: dict[str, str],
    planning_mode: str,
) -> ToolPlanResponse:
    cleaned_target = inferred_request.target
    cleaned_target = ENVIRONMENT_SEGMENT_PATTERN.sub("", cleaned_target).strip(" .")
    if inferred_request.tool_name == "document_search" and "filename" in arguments:
        cleaned_target = cleaned_target.replace(arguments["filename"], "").strip(" .")
        cleaned_target = re.sub(
            r"\b(for|in|inside|within)\b",
            "",
            cleaned_target,
            flags=re.IGNORECASE,
        ).strip(" .")
        if not cleaned_target:
            cleaned_target = "documents"
    if inferred_request.tool_name == "document_search" and "max_results" in arguments:
        cleaned_target = RESULT_LIMIT_PATTERN.sub("", cleaned_target).strip(" .")
        cleaned_target = re.sub(r"\band\s+show\b", "", cleaned_target, flags=re.IGNORECASE).strip(" .")
        if not cleaned_target:
            cleaned_target = "documents"

    planner_label = "llm planner" if planning_mode.startswith("llm_") else "local heuristic planner"

    return ToolPlanResponse(
        question=question.strip(),
        planning_mode=planning_mode,
        route_hint="tool_execution",
        tool_name=inferred_request.tool_name,
        action=inferred_request.action,
        target=cleaned_target,
        arguments=arguments,
        plan_summary=(
            f"Plan {inferred_request.tool_name}:{inferred_request.action} for "
            f"{cleaned_target} using a {planner_label}."
        ),
    )


def _normalize_planned_request(
    question: str,
    inferred_request: InferredToolRequest,
    arguments: dict[str, str],
) -> tuple[InferredToolRequest, dict[str, str]]:
    normalized_arguments = dict(arguments)

    ticket_id = _extract_ticket_id_argument(question)
    if ticket_id and "ticket_id" not in normalized_arguments:
        normalized_arguments["ticket_id"] = ticket_id

    if inferred_request.tool_name == "ticketing" and inferred_request.action in {
        "check",
        "show",
        "inspect",
        "query",
    }:
        inferred_request = InferredToolRequest(
            tool_name=inferred_request.tool_name,
            action="query",
            target=inferred_request.target,
        )
    elif inferred_request.tool_name == "ticketing" and inferred_request.action == "list":
        inferred_request = InferredToolRequest(
            tool_name=inferred_request.tool_name,
            action="list",
            target="tickets",
        )

    if inferred_request.tool_name == "ticketing":
        extracted_ticket_arguments = _extract_ticket_update_arguments(question)
        for key, value in extracted_ticket_arguments.items():
            normalized_arguments.setdefault(key, value)
        if inferred_request.action == "list":
            if "severity" in normalized_arguments:
                normalized_arguments["severity_filter"] = normalized_arguments.pop("severity")
            if "environment" in normalized_arguments:
                normalized_arguments["environment_filter"] = normalized_arguments.pop("environment")
            target_filter = _extract_ticket_target_filter(question)
            if target_filter and "target_filter" not in normalized_arguments:
                normalized_arguments["target_filter"] = target_filter
            max_results = _extract_search_max_results_argument(question)
            if max_results and "max_results" not in normalized_arguments:
                normalized_arguments["max_results"] = max_results
        cleaned_ticket_target = _clean_ticket_target(
            question,
            inferred_request.target,
            inferred_request.action,
        )
        if _is_generic_ticket_target(cleaned_ticket_target):
            argument_target = _pop_ticket_target_argument(normalized_arguments)
            if argument_target:
                cleaned_ticket_target = _canonicalize_ticket_target(argument_target)

        inferred_request = InferredToolRequest(
            tool_name=inferred_request.tool_name,
            action=inferred_request.action,
            target=cleaned_ticket_target,
        )

    if inferred_request.tool_name == "system_status":
        requested_environment = normalized_arguments.get("environment", "").strip()
        if not requested_environment:
            extracted_environment = _extract_environment_argument(question)
            if extracted_environment:
                normalized_arguments["environment"] = extracted_environment
        elif requested_environment:
            normalized_arguments["environment"] = _normalize_environment_value(requested_environment)

    if inferred_request.tool_name == "service_dependencies":
        requested_environment = normalized_arguments.get("environment", "").strip()
        if not requested_environment:
            extracted_environment = _extract_environment_argument(question)
            if extracted_environment:
                normalized_arguments["environment"] = extracted_environment
        elif requested_environment:
            normalized_arguments["environment"] = _normalize_environment_value(requested_environment)

    if inferred_request.tool_name == "document_search":
        llm_query = normalized_arguments.pop("query", "").strip()
        if llm_query and inferred_request.target.strip().lower() in {
            "doc",
            "docs",
            "document",
            "documents",
        }:
            inferred_request = InferredToolRequest(
                tool_name=inferred_request.tool_name,
                action=inferred_request.action,
                target=llm_query,
            )
        elif llm_query and not inferred_request.target.strip():
            inferred_request = InferredToolRequest(
                tool_name=inferred_request.tool_name,
                action=inferred_request.action,
                target=llm_query,
            )

        filename = _extract_filename_argument(question)
        if filename and "filename" not in normalized_arguments:
            normalized_arguments["filename"] = filename
        max_results = _extract_search_max_results_argument(question)
        if max_results and "max_results" not in normalized_arguments:
            normalized_arguments["max_results"] = max_results

    return inferred_request, normalized_arguments


def _heuristic_tool_plan(question: str, planning_mode: str = "heuristic_stub") -> ToolPlanResponse:
    inferred_request = infer_tool_request(question)
    inferred_request, arguments = _normalize_planned_request(question, inferred_request, {})
    return _build_tool_plan_response(
        question=question,
        inferred_request=inferred_request,
        arguments=arguments,
        planning_mode=planning_mode,
    )


def _plan_tool_request_with_llm(question: str) -> ToolPlanResponse | None:
    planning_mode, llm_plan = generate_llm_tool_plan(question, SUPPORTED_TOOLS)
    if llm_plan is None:
        return _heuristic_tool_plan(question, planning_mode=planning_mode)

    tool_name = llm_plan["tool_name"].strip().lower()
    metadata = SUPPORTED_TOOLS.get(tool_name)
    if metadata is None:
        return _heuristic_tool_plan(question, planning_mode="heuristic_fallback_invalid_llm_plan")

    action = llm_plan["action"].strip().lower()
    supported_actions = metadata.get("supported_actions", [])
    if action not in supported_actions:
        return _heuristic_tool_plan(question, planning_mode="heuristic_fallback_invalid_llm_plan")

    inferred_request = InferredToolRequest(
        tool_name=tool_name,
        action=action,
        target=llm_plan["target"],
    )
    inferred_request, arguments = _normalize_planned_request(
        question,
        inferred_request,
        llm_plan.get("arguments", {}),
    )
    return _build_tool_plan_response(
        question=question,
        inferred_request=inferred_request,
        arguments=arguments,
        planning_mode=planning_mode,
    )


def plan_tool_request(question: str) -> ToolPlanResponse:
    """Create a structured tool plan from a natural-language tool request."""
    return _plan_tool_request_with_llm(question)
