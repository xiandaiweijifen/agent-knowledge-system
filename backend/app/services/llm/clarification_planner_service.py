import json

import httpx

from app.core.config import settings
from app.services.llm.planner_cache_service import (
    get_cached_planner_result,
    set_cached_planner_result,
)


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_GENERATE_CONTENT_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/{model_name}:generateContent"
)


def _resolve_openai_clarification_planner_model() -> str:
    return settings.openai_clarification_planner_model.strip() or settings.openai_chat_model


def _resolve_gemini_clarification_planner_model() -> str:
    return settings.gemini_clarification_planner_model.strip() or settings.gemini_chat_model


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```JSON").removeprefix("```")
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_clarification_prompt(
    *,
    mode: str,
    question: str,
    search_query: str | None = None,
    next_action_question: str | None = None,
) -> str:
    scenario_lines = [
        "You are a clarification planner for an enterprise agent system.",
        "Return JSON only with keys: missing_fields, follow_up_questions, clarification_summary.",
        "missing_fields must be an array of short snake_case field names.",
        "follow_up_questions must be an array of short user-facing questions.",
        "clarification_summary must be a one-sentence explanation.",
        "Do not mark a field as missing if the user already provided it explicitly.",
    ]

    if mode == "general":
        scenario_lines.append(
            "The user request is underspecified. Identify the minimum missing fields needed to proceed safely."
        )
        scenario_lines.append(f"User request: {question}")
    elif mode == "search_then_action_miss":
        scenario_lines.append(
            "A search step found no supporting documents before an action step. "
            "Ask for query refinement and execution confirmation before continuing."
        )
        scenario_lines.append(f"Search query: {search_query or ''}")
        scenario_lines.append(f"Planned action request: {next_action_question or ''}")
    elif mode == "search_then_summary_miss":
        scenario_lines.append(
            "A search step found no supporting documents before a summary step. "
            "Ask for search refinement or document scope."
        )
        scenario_lines.append(f"Search query: {search_query or ''}")
    else:
        scenario_lines.append(f"User request: {question}")

    return "\n".join(scenario_lines)


def _normalize_clarification_payload(payload: dict) -> dict | None:
    missing_fields = payload.get("missing_fields", [])
    follow_up_questions = payload.get("follow_up_questions", [])
    clarification_summary = payload.get("clarification_summary")

    if not isinstance(missing_fields, list) or not isinstance(follow_up_questions, list):
        return None
    if not isinstance(clarification_summary, str) or not clarification_summary.strip():
        return None

    normalized_missing_fields = [
        item.strip()
        for item in missing_fields
        if isinstance(item, str) and item.strip()
    ]
    normalized_follow_up_questions = [
        item.strip()
        for item in follow_up_questions
        if isinstance(item, str) and item.strip()
    ]

    if not normalized_missing_fields or not normalized_follow_up_questions:
        return None

    return {
        "missing_fields": normalized_missing_fields,
        "follow_up_questions": normalized_follow_up_questions,
        "clarification_summary": clarification_summary.strip(),
    }


def _parse_llm_clarification_response(raw_text: str) -> dict | None:
    cleaned = _strip_json_fences(raw_text)
    if not cleaned:
        return None

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return _normalize_clarification_payload(payload)


def _generate_openai_clarification_plan(prompt: str) -> dict | None:
    model_name = _resolve_openai_clarification_planner_model()
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
                {"role": "user", "content": prompt},
            ],
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        return None
    return _parse_llm_clarification_response(content)


def _generate_gemini_clarification_plan(prompt: str) -> dict | None:
    model_name = _resolve_gemini_clarification_planner_model()
    response = httpx.post(
        GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(model_name=model_name),
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["candidates"][0]["content"]["parts"][0]["text"]
    if not isinstance(content, str):
        return None
    return _parse_llm_clarification_response(content)


def generate_llm_clarification_plan(
    *,
    mode: str,
    question: str,
    search_query: str | None = None,
    next_action_question: str | None = None,
) -> tuple[str, dict | None]:
    provider = settings.clarification_planner_provider.lower().strip()
    if provider == "fallback":
        return "heuristic_stub", None

    cache_payload = {
        "provider": provider,
        "mode": mode,
        "question": question,
        "search_query": search_query or "",
        "next_action_question": next_action_question or "",
    }
    cached_plan = get_cached_planner_result("clarification_planner", cache_payload)
    if cached_plan is not None:
        return f"llm_{provider}", cached_plan

    prompt = _build_clarification_prompt(
        mode=mode,
        question=question,
        search_query=search_query,
        next_action_question=next_action_question,
    )

    try:
        if provider == "openai":
            if not settings.openai_api_key:
                return "heuristic_fallback_missing_openai_key", None
            plan = _generate_openai_clarification_plan(prompt)
            if plan is not None:
                set_cached_planner_result("clarification_planner", cache_payload, plan)
            return "llm_openai", plan

        if provider == "gemini":
            if not settings.gemini_api_key:
                return "heuristic_fallback_missing_gemini_key", None
            plan = _generate_gemini_clarification_plan(prompt)
            if plan is not None:
                set_cached_planner_result("clarification_planner", cache_payload, plan)
            return "llm_gemini", plan
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return f"heuristic_fallback_after_{provider}_error", None

    return "heuristic_fallback_unsupported_provider", None
