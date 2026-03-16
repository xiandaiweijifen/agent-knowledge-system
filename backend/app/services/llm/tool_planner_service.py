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


def _resolve_openai_tool_planner_model() -> str:
    return settings.openai_tool_planner_model.strip() or settings.openai_chat_model


def _resolve_gemini_tool_planner_model() -> str:
    return settings.gemini_tool_planner_model.strip() or settings.gemini_chat_model


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```JSON").removeprefix("```")
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_tool_planner_prompt(question: str, supported_tools: dict[str, dict[str, object]]) -> str:
    tool_catalog = []
    for tool_name, metadata in supported_tools.items():
        supported_actions = metadata.get("supported_actions", [])
        tool_catalog.append(
            {
                "tool_name": tool_name,
                "supported_actions": supported_actions,
                "description": metadata.get("description", ""),
            }
        )

    return (
        "You are a tool planning assistant for an enterprise agent system. "
        "Convert the user request into a single structured tool plan. "
        "Return JSON only with keys: tool_name, action, target, arguments. "
        "The arguments value must be an object with string values only. "
        "Do not include markdown fences or explanations.\n\n"
        f"Supported tools:\n{json.dumps(tool_catalog, ensure_ascii=False, indent=2)}\n\n"
        "Planning rules:\n"
        "- Choose exactly one tool.\n"
        "- Use only listed tool_name values and supported actions.\n"
        "- Keep target concise and specific.\n"
        "- If the request implies no extra arguments, return an empty object.\n"
        "- Preserve filename filters, ticket ids, environment, severity, status, "
        "max_results, and target_filter when clearly present.\n\n"
        f"User request: {question}"
    )


def _normalize_plan_payload(payload: dict) -> dict[str, str] | None:
    tool_name = payload.get("tool_name")
    action = payload.get("action")
    target = payload.get("target")
    arguments = payload.get("arguments", {})

    if not all(isinstance(value, str) and value.strip() for value in (tool_name, action, target)):
        return None

    if not isinstance(arguments, dict):
        return None

    normalized_arguments: dict[str, str] = {}
    for key, value in arguments.items():
        if not isinstance(key, str):
            return None
        if isinstance(value, str):
            cleaned_value = value.strip()
        elif isinstance(value, (int, float, bool)):
            cleaned_value = str(value).lower() if isinstance(value, bool) else str(value)
        else:
            return None
        if cleaned_value:
            normalized_arguments[key.strip()] = cleaned_value

    return {
        "tool_name": tool_name.strip(),
        "action": action.strip(),
        "target": target.strip(),
        "arguments": normalized_arguments,
    }


def _parse_llm_plan_response(raw_text: str) -> dict[str, str] | None:
    cleaned = _strip_json_fences(raw_text)
    if not cleaned:
        return None

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return _normalize_plan_payload(payload)


def _generate_openai_tool_plan(question: str, supported_tools: dict[str, dict[str, object]]) -> dict | None:
    model_name = _resolve_openai_tool_planner_model()
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
                {
                    "role": "system",
                    "content": "Return valid JSON only.",
                },
                {
                    "role": "user",
                    "content": _build_tool_planner_prompt(question, supported_tools),
                },
            ],
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        return None
    return _parse_llm_plan_response(content)


def _generate_gemini_tool_plan(question: str, supported_tools: dict[str, dict[str, object]]) -> dict | None:
    model_name = _resolve_gemini_tool_planner_model()
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
                            "text": _build_tool_planner_prompt(question, supported_tools),
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
            },
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["candidates"][0]["content"]["parts"][0]["text"]
    if not isinstance(content, str):
        return None
    return _parse_llm_plan_response(content)


def generate_llm_tool_plan(
    question: str,
    supported_tools: dict[str, dict[str, object]],
) -> tuple[str, dict | None]:
    provider = settings.tool_planner_provider.lower().strip()

    if provider == "fallback":
        return "heuristic_stub", None

    cache_payload = {
        "provider": provider,
        "question": question,
        "supported_tools": supported_tools,
    }
    cached_plan = get_cached_planner_result("tool_planner", cache_payload)
    if cached_plan is not None:
        return f"llm_{provider}", cached_plan

    try:
        if provider == "openai":
            if not settings.openai_api_key:
                return "heuristic_fallback_missing_openai_key", None
            plan = _generate_openai_tool_plan(question, supported_tools)
            if plan is not None:
                set_cached_planner_result("tool_planner", cache_payload, plan)
            return "llm_openai", plan

        if provider == "gemini":
            if not settings.gemini_api_key:
                return "heuristic_fallback_missing_gemini_key", None
            plan = _generate_gemini_tool_plan(question, supported_tools)
            if plan is not None:
                set_cached_planner_result("tool_planner", cache_payload, plan)
            return "llm_gemini", plan
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return f"heuristic_fallback_after_{provider}_error", None

    return "heuristic_fallback_unsupported_provider", None
