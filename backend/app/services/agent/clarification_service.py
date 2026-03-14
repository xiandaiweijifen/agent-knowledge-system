from app.schemas.clarification import ClarificationPlanResponse


def plan_clarification(question: str) -> ClarificationPlanResponse:
    """Return a structured clarification plan for underspecified requests."""
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
        planning_mode="heuristic_stub",
        missing_fields=missing_fields,
        follow_up_questions=follow_up_questions,
        clarification_summary=(
            "The request is underspecified and should be clarified before the workflow "
            "continues."
        ),
    )
