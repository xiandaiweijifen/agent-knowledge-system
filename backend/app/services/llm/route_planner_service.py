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
SUPPORTED_ROUTES = {
    "knowledge_retrieval",
    "tool_execution",
    "clarification_needed",
}


def _resolve_openai_route_planner_model() -> str:
    return settings.openai_route_planner_model.strip() or settings.openai_chat_model


def _resolve_gemini_route_planner_model() -> str:
    return settings.gemini_route_planner_model.strip() or settings.gemini_chat_model


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```JSON").removeprefix("```")
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_route_planner_prompt(question: str, filename: str | None = None) -> str:
    filename_hint = f"Document context: {filename}" if filename else "Document context: none"
    return (
        "You are a routing assistant for an enterprise agent system. "
        "Classify the request into exactly one next-step route. "
        "Choose knowledge_retrieval for document-backed questions, "
        "tool_execution for action-oriented tool requests, and "
        "clarification_needed for underspecified or ambiguous requests.\n"
        f"{filename_hint}\n\n"
        f"User request: {question}"
    )


def _normalize_route_payload(payload: dict) -> dict[str, str] | None:
    route = payload.get("route") or payload.get("route_type")
    route_reason = payload.get("route_reason") or payload.get("reason")

    if not isinstance(route, str):
        return None
    normalized_route = route.strip().lower()
    if normalized_route not in SUPPORTED_ROUTES:
        return None

    if not isinstance(route_reason, str) or not route_reason.strip():
        return None

    return {
        "route": normalized_route,
        "route_reason": route_reason.strip(),
    }


def _parse_llm_route_response(raw_text: str) -> dict[str, str] | None:
    cleaned = _strip_json_fences(raw_text)
    if not cleaned:
        return None

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return _normalize_route_payload(payload)


def _extract_openai_tool_call_arguments(payload: dict) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return None

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        first_tool_call = tool_calls[0]
        if isinstance(first_tool_call, dict):
            function_payload = first_tool_call.get("function", {})
            if isinstance(function_payload, dict):
                arguments = function_payload.get("arguments")
                if isinstance(arguments, str):
                    return arguments

    content = message.get("content")
    return content if isinstance(content, str) else None


def _generate_openai_route_decision(question: str, filename: str | None = None) -> dict[str, str] | None:
    model_name = _resolve_openai_route_planner_model()
    response = httpx.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "temperature": 0,
            "tool_choice": {
                "type": "function",
                "function": {"name": "route_request"},
            },
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "route_request",
                        "description": "Classify the next runtime route for the user request.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "route": {
                                    "type": "string",
                                    "enum": sorted(SUPPORTED_ROUTES),
                                },
                                "route_reason": {
                                    "type": "string",
                                },
                            },
                            "required": ["route", "route_reason"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "messages": [
                {
                    "role": "system",
                    "content": "Use the provided tool to return the route decision.",
                },
                {
                    "role": "user",
                    "content": _build_route_planner_prompt(question, filename),
                },
            ],
        },
        timeout=30.0,
    )
    response.raise_for_status()
    arguments = _extract_openai_tool_call_arguments(response.json())
    if not isinstance(arguments, str):
        return None
    return _parse_llm_route_response(arguments)


def _extract_text_from_candidate_payload(payload):
    texts: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "text" and isinstance(value, str) and value.strip():
                texts.append(value)
            else:
                texts.extend(_extract_text_from_candidate_payload(value))
    elif isinstance(payload, list):
        for item in payload:
            texts.extend(_extract_text_from_candidate_payload(item))
    return texts


def _generate_gemini_route_decision(question: str, filename: str | None = None) -> dict[str, str] | None:
    model_name = _resolve_gemini_route_planner_model()
    response = httpx.post(
        GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(model_name=model_name),
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                _build_route_planner_prompt(question, filename)
                                + "\n\nReturn JSON only with keys: route, route_reason."
                            ),
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return None

    texts: list[str] = []
    for candidate in candidates:
        texts.extend(_extract_text_from_candidate_payload(candidate))
    if not texts:
        return None
    return _parse_llm_route_response("\n".join(texts).strip())


def generate_llm_route_decision(
    question: str,
    filename: str | None = None,
) -> tuple[str, dict[str, str] | None]:
    provider = settings.route_planner_provider.lower().strip()

    if provider == "fallback":
        return "heuristic_legacy_router", None

    cache_payload = {
        "provider": provider,
        "question": question,
        "filename": filename or "",
    }
    cached_route = get_cached_planner_result("route_planner", cache_payload)
    if cached_route is not None:
        return f"llm_{provider}", cached_route

    try:
        if provider == "openai":
            if not settings.openai_api_key:
                return "heuristic_fallback_missing_openai_key", None
            route = _generate_openai_route_decision(question, filename)
            if route is not None:
                set_cached_planner_result("route_planner", cache_payload, route)
            return "llm_openai", route

        if provider == "gemini":
            if not settings.gemini_api_key:
                return "heuristic_fallback_missing_gemini_key", None
            route = _generate_gemini_route_decision(question, filename)
            if route is not None:
                set_cached_planner_result("route_planner", cache_payload, route)
            return "llm_gemini", route
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return f"heuristic_fallback_after_{provider}_error", None

    return "heuristic_fallback_unsupported_provider", None
