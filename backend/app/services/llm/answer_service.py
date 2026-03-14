import httpx
from time import perf_counter

from app.core.config import settings
from app.services.ingestion.document_service import build_utc_timestamp


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_GENERATE_CONTENT_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/{model_name}:generateContent"
)


def build_context_block(matches: list[dict]) -> str:
    """Build a compact context block from retrieved chunks."""
    context_sections = []

    for match in matches:
        context_sections.append(
            "\n".join(
                [
                    f"[{match['chunk_id']}]",
                    match["content"],
                ]
            )
        )

    return "\n\n".join(context_sections)


def build_fallback_answer(question: str, matches: list[dict]) -> str:
    """Return a local placeholder answer when no LLM call is available."""
    if not matches:
        return "No relevant context was retrieved for the question."

    cited_chunks = ", ".join(match["chunk_id"] for match in matches[:3])
    return (
        "Retrieved relevant context for the question, but LLM answer generation "
        f"is using local fallback right now. Top supporting chunks: {cited_chunks}. "
        f"Question: {question}"
    )


def build_answer_result(
    answer: str,
    answer_source: str,
    chat_provider: str,
    chat_model: str,
    answer_started: float,
) -> dict:
    """Build a normalized answer payload with tracing metadata."""
    return {
        "answer": answer,
        "answer_source": answer_source,
        "model": chat_model,
        "chat_provider": chat_provider,
        "chat_model": chat_model,
        "answered_at": build_utc_timestamp(),
        "answer_latency_ms": round((perf_counter() - answer_started) * 1000, 3),
    }


def generate_openai_answer(question: str, matches: list[dict], answer_started: float) -> dict:
    """Generate a RAG answer with OpenAI chat completions."""
    context_block = build_context_block(matches)
    payload = {
        "model": settings.openai_chat_model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an enterprise knowledge assistant. Answer the question "
                    "using only the provided context. If the context is insufficient, "
                    "say so explicitly."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Context:\n{context_block}"
                ),
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        response_payload = response.json()
        answer = response_payload["choices"][0]["message"]["content"].strip()
        return build_answer_result(
            answer=answer,
            answer_source="openai",
            chat_provider="openai",
            chat_model=settings.openai_chat_model,
            answer_started=answer_started,
        )
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        return build_answer_result(
            answer=build_fallback_answer(question, matches),
            answer_source="fallback_after_openai_error",
            chat_provider="fallback_after_openai_error",
            chat_model=settings.openai_chat_model,
            answer_started=answer_started,
        )


def generate_gemini_answer(question: str, matches: list[dict], answer_started: float) -> dict:
    """Generate a RAG answer with Gemini generateContent."""
    context_block = build_context_block(matches)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "You are an enterprise knowledge assistant. Answer the "
                            "question using only the provided context. If the context "
                            "is insufficient, say so explicitly.\n\n"
                            f"Question:\n{question}\n\n"
                            f"Context:\n{context_block}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
        },
    }

    try:
        response = httpx.post(
            GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(
                model_name=settings.gemini_chat_model,
            ),
            headers={
                "x-goog-api-key": settings.gemini_api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        response_payload = response.json()
        answer = response_payload["candidates"][0]["content"]["parts"][0]["text"].strip()
        return build_answer_result(
            answer=answer,
            answer_source="gemini",
            chat_provider="gemini",
            chat_model=settings.gemini_chat_model,
            answer_started=answer_started,
        )
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        return build_answer_result(
            answer=build_fallback_answer(question, matches),
            answer_source="fallback_after_gemini_error",
            chat_provider="fallback_after_gemini_error",
            chat_model=settings.gemini_chat_model,
            answer_started=answer_started,
        )


def generate_rag_answer(question: str, matches: list[dict]) -> dict:
    """Generate a RAG answer from retrieved chunks."""
    answer_started = perf_counter()
    provider = settings.chat_provider.lower().strip()

    if provider == "fallback":
        return build_answer_result(
            answer=build_fallback_answer(question, matches),
            answer_source="fallback",
            chat_provider="fallback",
            chat_model="local-fallback",
            answer_started=answer_started,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            return build_answer_result(
                answer=build_fallback_answer(question, matches),
                answer_source="fallback_missing_openai_key",
                chat_provider="fallback_missing_openai_key",
                chat_model=settings.openai_chat_model,
                answer_started=answer_started,
            )
        return generate_openai_answer(question, matches, answer_started)

    if provider == "gemini":
        if not settings.gemini_api_key:
            return build_answer_result(
                answer=build_fallback_answer(question, matches),
                answer_source="fallback_missing_gemini_key",
                chat_provider="fallback_missing_gemini_key",
                chat_model=settings.gemini_chat_model,
                answer_started=answer_started,
            )
        return generate_gemini_answer(question, matches, answer_started)

    return build_answer_result(
        answer=build_fallback_answer(question, matches),
        answer_source="fallback_unsupported_chat_provider",
        chat_provider="fallback_unsupported_chat_provider",
        chat_model="local-fallback",
        answer_started=answer_started,
    )
