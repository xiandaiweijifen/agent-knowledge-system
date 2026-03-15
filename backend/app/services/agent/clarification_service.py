from app.schemas.clarification import ClarificationPlanResponse
from app.services.llm.clarification_planner_service import generate_llm_clarification_plan


def _filter_follow_up_questions(
    follow_up_questions: list[str],
    removed_fields: set[str],
) -> list[str]:
    filtered_questions: list[str] = []
    for question in follow_up_questions:
        lowered = question.lower()
        if "environment" in removed_fields and "environment" in lowered:
            continue
        if "priority" in removed_fields and ("priority" in lowered or "severity" in lowered):
            continue
        if "target" in removed_fields and any(
            token in lowered for token in ("service", "system", "resource", "target")
        ):
            continue
        filtered_questions.append(question)
    return filtered_questions


def _normalize_general_llm_clarification_plan(
    question: str,
    missing_fields: list[str],
    follow_up_questions: list[str],
    clarification_summary: str,
) -> tuple[list[str], list[str], str]:
    lowered = question.lower()
    normalized_missing_fields = [field for field in missing_fields if field]
    removed_fields: set[str] = set()

    if any(env in lowered for env in ("production", "staging", "development", "dev")):
        if "environment" in normalized_missing_fields:
            normalized_missing_fields = [field for field in normalized_missing_fields if field != "environment"]
            removed_fields.add("environment")

    if any(priority in lowered for priority in ("high", "medium", "low", "severity", "priority")):
        if "priority" in normalized_missing_fields:
            normalized_missing_fields = [field for field in normalized_missing_fields if field != "priority"]
            removed_fields.add("priority")

    if any(token in lowered for token in ("service", "system", "database")) or "-" in lowered:
        if "target" in normalized_missing_fields:
            normalized_missing_fields = [field for field in normalized_missing_fields if field != "target"]
            removed_fields.add("target")

    filtered_questions = _filter_follow_up_questions(follow_up_questions, removed_fields)

    if not normalized_missing_fields:
        normalized_missing_fields = ["task_details"]
        filtered_questions = ["What exact action should the agent perform?"]
        clarification_summary = (
            "The request still needs the exact action before the workflow can continue."
        )

    if not filtered_questions:
        filtered_questions = ["What exact action should the agent perform?"]

    return normalized_missing_fields, filtered_questions, clarification_summary


def _heuristic_plan_clarification(
    question: str,
    planning_mode: str = "heuristic_stub",
) -> ClarificationPlanResponse:
    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError("question_must_not_be_empty")

    lowered = normalized_question.lower()
    missing_fields: list[str] = []
    follow_up_questions: list[str] = []

    if "service" not in lowered and "system" not in lowered and "database" not in lowered:
        missing_fields.append("target")
        follow_up_questions.append("Which service, system, or resource should the agent act on?")

    if "production" not in lowered and "staging" not in lowered and "dev" not in lowered:
        missing_fields.append("environment")
        follow_up_questions.append("Which environment should the action apply to?")

    if "high" not in lowered and "medium" not in lowered and "low" not in lowered:
        missing_fields.append("priority")
        follow_up_questions.append("What priority or severity should the action use?")

    if not missing_fields:
        missing_fields.append("task_details")
        follow_up_questions.append("What exact action should the agent perform?")

    return ClarificationPlanResponse(
        question=normalized_question,
        planning_mode=planning_mode,
        missing_fields=missing_fields,
        follow_up_questions=follow_up_questions,
        clarification_summary=(
            "The request is underspecified and should be clarified before the workflow "
            "continues."
        ),
    )


def _heuristic_plan_search_miss_clarification(
    search_query: str,
    next_action_question: str,
    planning_mode: str = "heuristic_stub",
) -> ClarificationPlanResponse:
    normalized_search_query = search_query.strip()
    normalized_action = next_action_question.strip()

    if not normalized_search_query or not normalized_action:
        raise ValueError("search_query_and_action_must_not_be_empty")

    follow_up_questions = [
        f"I could not find supporting documents for '{normalized_search_query}'. "
        "Should I search a different phrase or document set?",
        "Do you still want me to continue with the action even without supporting documentation?",
    ]

    lowered_action = normalized_action.lower()
    missing_fields = ["search_query_refinement", "execution_confirmation"]

    if "production" not in lowered_action and "staging" not in lowered_action and "dev" not in lowered_action:
        missing_fields.append("environment")
        follow_up_questions.append("Which environment should the action apply to?")

    return ClarificationPlanResponse(
        question=normalized_action,
        planning_mode=planning_mode,
        missing_fields=missing_fields,
        follow_up_questions=follow_up_questions,
        clarification_summary=(
            "The workflow could not find supporting documents for the search step, so it should "
            "be clarified before continuing to execution."
        ),
    )


def _heuristic_plan_search_summary_miss_clarification(
    search_query: str,
    planning_mode: str = "heuristic_stub",
) -> ClarificationPlanResponse:
    normalized_search_query = search_query.strip()

    if not normalized_search_query:
        raise ValueError("search_query_must_not_be_empty")

    return ClarificationPlanResponse(
        question=normalized_search_query,
        planning_mode=planning_mode,
        missing_fields=["search_query_refinement", "document_scope"],
        follow_up_questions=[
            f"I could not find supporting documents for '{normalized_search_query}'. Should I search a different phrase?",
            "Should I narrow the search to a specific document or file?",
        ],
        clarification_summary=(
            "The workflow could not find supporting documents to summarize, so it should be "
            "clarified before continuing."
        ),
    )


def plan_clarification(question: str) -> ClarificationPlanResponse:
    """Return a structured clarification plan for underspecified requests."""
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question_must_not_be_empty")

    planning_mode, llm_plan = generate_llm_clarification_plan(
        mode="general",
        question=normalized_question,
    )
    if llm_plan is None:
        return _heuristic_plan_clarification(normalized_question, planning_mode=planning_mode)

    missing_fields, follow_up_questions, clarification_summary = _normalize_general_llm_clarification_plan(
        normalized_question,
        llm_plan["missing_fields"],
        llm_plan["follow_up_questions"],
        llm_plan["clarification_summary"],
    )

    return ClarificationPlanResponse(
        question=normalized_question,
        planning_mode=planning_mode,
        missing_fields=missing_fields,
        follow_up_questions=follow_up_questions,
        clarification_summary=clarification_summary,
    )


def plan_search_miss_clarification(
    search_query: str,
    next_action_question: str,
) -> ClarificationPlanResponse:
    """Return a targeted clarification plan when a search step finds no support."""
    normalized_search_query = search_query.strip()
    normalized_action = next_action_question.strip()

    if not normalized_search_query or not normalized_action:
        raise ValueError("search_query_and_action_must_not_be_empty")

    planning_mode, llm_plan = generate_llm_clarification_plan(
        mode="search_then_action_miss",
        question=normalized_action,
        search_query=normalized_search_query,
        next_action_question=normalized_action,
    )
    if llm_plan is None:
        return _heuristic_plan_search_miss_clarification(
            normalized_search_query,
            normalized_action,
            planning_mode=planning_mode,
        )

    return ClarificationPlanResponse(
        question=normalized_action,
        planning_mode=planning_mode,
        missing_fields=llm_plan["missing_fields"],
        follow_up_questions=llm_plan["follow_up_questions"],
        clarification_summary=llm_plan["clarification_summary"],
    )


def plan_search_summary_miss_clarification(search_query: str) -> ClarificationPlanResponse:
    """Return a targeted clarification plan when a search-to-summary step finds no support."""
    normalized_search_query = search_query.strip()
    if not normalized_search_query:
        raise ValueError("search_query_must_not_be_empty")

    planning_mode, llm_plan = generate_llm_clarification_plan(
        mode="search_then_summary_miss",
        question=normalized_search_query,
        search_query=normalized_search_query,
    )
    if llm_plan is None:
        return _heuristic_plan_search_summary_miss_clarification(
            normalized_search_query,
            planning_mode=planning_mode,
        )

    return ClarificationPlanResponse(
        question=normalized_search_query,
        planning_mode=planning_mode,
        missing_fields=llm_plan["missing_fields"],
        follow_up_questions=llm_plan["follow_up_questions"],
        clarification_summary=llm_plan["clarification_summary"],
    )


def plan_unsupported_action_clarification(question: str, target: str) -> ClarificationPlanResponse:
    normalized_question = question.strip()
    normalized_target = target.strip() or "the target system"

    if not normalized_question:
        raise ValueError("question_must_not_be_empty")

    return ClarificationPlanResponse(
        question=normalized_question,
        planning_mode="guardrail_stub",
        missing_fields=["execution_confirmation", "fallback_action"],
        follow_up_questions=[
            f"I cannot directly execute that action for {normalized_target} yet. Do you want me to create a ticket instead?",
            "If you do not want a ticket, what supported action should I take instead?",
        ],
        clarification_summary=(
            "The request asks for a direct operational action that this system does not execute yet, "
            "so it should be clarified before continuing."
        ),
    )
