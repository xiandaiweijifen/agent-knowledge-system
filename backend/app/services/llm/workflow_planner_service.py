import json

import httpx

from app.core.config import settings


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_GENERATE_CONTENT_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/{model_name}:generateContent"
)


def _resolve_openai_workflow_planner_model() -> str:
    return settings.openai_workflow_planner_model.strip() or settings.openai_chat_model


def _resolve_gemini_workflow_planner_model() -> str:
    return settings.gemini_workflow_planner_model.strip() or settings.gemini_chat_model


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```JSON").removeprefix("```")
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_workflow_planner_prompt(question: str) -> str:
    return (
        "You are a workflow planning assistant for an enterprise agent system. "
        "Decide whether the user request should stay single-step or be decomposed into a search-first workflow. "
        "Return JSON only with keys: workflow_kind, search_question, follow_up_question. "
        "workflow_kind must be one of: single_step, search_then_ticket, search_then_summarize. "
        "If workflow_kind is single_step, return empty strings for search_question and follow_up_question. "
        "If workflow_kind is search_then_ticket, search_question must contain the search step and "
        "follow_up_question must contain the ticket action step. "
        "If workflow_kind is search_then_summarize, search_question must contain the search step and "
        "follow_up_question must contain the summary step. "
        "Preserve clear user constraints like filename, max_results, severity, environment, and target. "
        "Do not include markdown fences or explanations.\n\n"
        f"User request: {question}"
    )


def _normalize_workflow_plan_payload(payload: dict) -> dict[str, str] | None:
    workflow_kind = payload.get("workflow_kind")
    search_question = payload.get("search_question", "")
    follow_up_question = payload.get("follow_up_question", "")

    if not isinstance(workflow_kind, str):
        return None
    normalized_kind = workflow_kind.strip()
    if normalized_kind not in {"single_step", "search_then_ticket", "search_then_summarize"}:
        return None

    if not isinstance(search_question, str) or not isinstance(follow_up_question, str):
        return None

    normalized_payload = {
        "workflow_kind": normalized_kind,
        "search_question": search_question.strip(),
        "follow_up_question": follow_up_question.strip(),
    }

    if normalized_kind == "single_step":
        return normalized_payload

    if not normalized_payload["search_question"] or not normalized_payload["follow_up_question"]:
        return None

    return normalized_payload


def _parse_llm_workflow_plan_response(raw_text: str) -> dict[str, str] | None:
    cleaned = _strip_json_fences(raw_text)
    if not cleaned:
        return None

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return _normalize_workflow_plan_payload(payload)


def _generate_openai_workflow_plan(question: str) -> dict[str, str] | None:
    model_name = _resolve_openai_workflow_planner_model()
    response = httpx.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": _build_workflow_planner_prompt(question)},
            ],
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        return None
    return _parse_llm_workflow_plan_response(content)


def _generate_gemini_workflow_plan(question: str) -> dict[str, str] | None:
    model_name = _resolve_gemini_workflow_planner_model()
    response = httpx.post(
        GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(model_name=model_name),
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [{"role": "user", "parts": [{"text": _build_workflow_planner_prompt(question)}]}],
            "generationConfig": {"temperature": 0},
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["candidates"][0]["content"]["parts"][0]["text"]
    if not isinstance(content, str):
        return None
    return _parse_llm_workflow_plan_response(content)


def generate_llm_workflow_plan(question: str) -> tuple[str, dict[str, str] | None]:
    provider = settings.workflow_planner_provider.lower().strip()

    if provider == "fallback":
        return "heuristic_stub", None

    try:
        if provider == "openai":
            if not settings.openai_api_key:
                return "heuristic_fallback_missing_openai_key", None
            return "llm_openai", _generate_openai_workflow_plan(question)

        if provider == "gemini":
            if not settings.gemini_api_key:
                return "heuristic_fallback_missing_gemini_key", None
            return "llm_gemini", _generate_gemini_workflow_plan(question)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return f"heuristic_fallback_after_{provider}_error", None

    return "heuristic_fallback_unsupported_provider", None
