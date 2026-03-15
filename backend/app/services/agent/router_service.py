import re

from app.schemas.query import RouteDecision


TOOL_ACTION_PATTERN = re.compile(
    r"\b(create|open|close|deploy|restart|rollback|run|execute|trigger|query|update|delete|search|find|check|show|inspect|lookup|look\s+up|list|set|move)\b",
    re.IGNORECASE,
)
AMBIGUOUS_ACTION_PATTERN = re.compile(
    r"\b(do|handle|fix|resolve)\b",
    re.IGNORECASE,
)
TOOL_TARGET_PATTERN = re.compile(
    r"\b(ticket|incident|deployment|service|database|api|job|workflow|pipeline|record|status|health|config|document|doc|docs)\b",
    re.IGNORECASE,
)
SEARCH_STYLE_ACTION_PATTERN = re.compile(
    r"\b(search|find|lookup|look up|show|inspect|check|query|list|set|move)\b",
    re.IGNORECASE,
)
AMBIGUOUS_REFERENCE_PATTERN = re.compile(
    r"\b(this|that|it|them|those|these)\b",
    re.IGNORECASE,
)


def route_request(question: str, filename: str | None = None) -> RouteDecision:
    """Classify a request into the next system path."""
    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError("question_must_not_be_empty")

    lowered = normalized_question.lower()

    if AMBIGUOUS_REFERENCE_PATTERN.search(lowered) and AMBIGUOUS_ACTION_PATTERN.search(lowered):
        return RouteDecision(
            route_type="clarification_needed",
            route_reason=(
                "The request refers to an action with an ambiguous reference, so the system "
                "should ask for clarification before proceeding."
            ),
            filename=filename,
        )

    if TOOL_ACTION_PATTERN.search(lowered):
        if SEARCH_STYLE_ACTION_PATTERN.search(lowered):
            return RouteDecision(
                route_type="tool_execution",
                route_reason=(
                    "The request asks the system to inspect, search, or check an external "
                    "resource, so it should be routed toward tool execution."
                ),
                filename=filename,
            )

        if AMBIGUOUS_REFERENCE_PATTERN.search(lowered) and not TOOL_TARGET_PATTERN.search(lowered):
            return RouteDecision(
                route_type="clarification_needed",
                route_reason=(
                    "The request implies an action, but the target is underspecified and "
                    "should be clarified before execution."
                ),
                filename=filename,
            )

        if TOOL_TARGET_PATTERN.search(lowered):
            return RouteDecision(
                route_type="tool_execution",
                route_reason=(
                    "The request contains an execution verb and an external system target, "
                    "so it should be routed toward tool execution."
                ),
                filename=filename,
            )

    return RouteDecision(
        route_type="knowledge_retrieval",
        route_reason=(
            "The request is best handled as a knowledge query and should continue through "
            "retrieval and answer generation."
        ),
        filename=filename,
    )
