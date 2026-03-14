import httpx
from time import perf_counter

from app.core.config import settings
from app.services.ingestion.document_service import build_utc_timestamp


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


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


def generate_rag_answer(question: str, matches: list[dict]) -> dict:
    """Generate a RAG answer from retrieved chunks."""
    answer_started = perf_counter()

    if not settings.openai_api_key:
        return {
            "answer": build_fallback_answer(question, matches),
            "answer_source": "fallback",
            "model": "local-fallback",
            "chat_provider": "fallback",
            "chat_model": "local-fallback",
            "answered_at": build_utc_timestamp(),
            "answer_latency_ms": round((perf_counter() - answer_started) * 1000, 3),
        }

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
        return {
            "answer": answer,
            "answer_source": "openai",
            "model": settings.openai_chat_model,
            "chat_provider": "openai",
            "chat_model": settings.openai_chat_model,
            "answered_at": build_utc_timestamp(),
            "answer_latency_ms": round((perf_counter() - answer_started) * 1000, 3),
        }
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        return {
            "answer": build_fallback_answer(question, matches),
            "answer_source": "fallback_after_openai_error",
            "model": settings.openai_chat_model,
            "chat_provider": "fallback_after_openai_error",
            "chat_model": settings.openai_chat_model,
            "answered_at": build_utc_timestamp(),
            "answer_latency_ms": round((perf_counter() - answer_started) * 1000, 3),
        }
