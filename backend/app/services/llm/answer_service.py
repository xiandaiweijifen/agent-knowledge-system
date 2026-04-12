import httpx
import re
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
        section_path = " / ".join(match.get("section_path", []))
        metadata_lines = [
            f"[{match['chunk_id']}]",
            f"Source File: {match.get('source_filename', 'unknown')}",
        ]
        if section_path:
            metadata_lines.append(f"Source Section: {section_path}")
        context_sections.append(
            "\n".join(
                [
                    *metadata_lines,
                    match["content"],
                ]
            )
        )

    return "\n\n".join(context_sections)


def _tokenize_overlap_text(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) >= 4
    }


def infer_answer_style(question: str, matches: list[dict]) -> str:
    """Infer a lightweight answer style from the question and retrieved metadata."""
    lowered_question = question.lower()
    section_text = " ".join(
        " ".join(match.get("section_path", [])) for match in matches
    ).lower()

    if any(keyword in lowered_question for keyword in ("runbook", "playbook")):
        return "runbook"
    if any(keyword in lowered_question for keyword in ("incident", "outage", "sev", "severity")):
        return "incident"
    if any(
        keyword in lowered_question
        for keyword in ("workflow", "recovery", "resume", "retry", "clarification")
    ) or "workflow" in section_text:
        return "workflow"
    return "concept"


def build_answer_instruction(answer_style: str) -> str:
    base_instruction = (
        "You are an enterprise knowledge assistant. Answer the question using "
        "only the provided context. Synthesize across source files and section "
        "titles when they are available. If the context is insufficient, say so "
        "explicitly. Do not ignore directly relevant runbook or section content "
        "that appears in the context."
    )

    style_instruction = {
        "runbook": (
            "Prefer a runbook-style answer: summarize actionable steps under short "
            "headings such as scope, triage, mitigation, and recovery confirmation "
            "when those sections exist in the context."
        ),
        "incident": (
            "Prefer an incident summary: highlight symptoms, likely impact, and the "
            "most relevant mitigation or response actions from the context."
        ),
        "workflow": (
            "Prefer a workflow explanation: describe sequence, decision points, and "
            "recovery or retry semantics in a structured way."
        ),
        "concept": (
            "Prefer a concise explanatory answer: define the concept first, then "
            "summarize the most important supporting details."
        ),
    }[answer_style]

    return f"{base_instruction} {style_instruction}"


def build_answer_citations(
    answer: str,
    matches: list[dict],
    limit: int = 3,
) -> list[dict]:
    """Build structured citations ranked by retrieval score and answer alignment."""
    citations: list[dict] = []
    seen_chunk_ids: set[str] = set()
    answer_tokens = _tokenize_overlap_text(answer)
    ranked_matches: list[tuple[float, dict]] = []

    for index, match in enumerate(matches):
        content_tokens = _tokenize_overlap_text(match.get("content", ""))
        section_tokens = _tokenize_overlap_text(" ".join(match.get("section_path", [])))
        overlap_count = len(answer_tokens & content_tokens)
        section_overlap_count = len(answer_tokens & section_tokens)
        match_score = float(match.get("score", 0.0))
        citation_score = (
            match_score
            + (overlap_count * 0.05)
            + (section_overlap_count * 0.08)
            - (index * 0.001)
        )
        ranked_matches.append((citation_score, match))

    ranked_matches.sort(key=lambda item: item[0], reverse=True)

    for _, match in ranked_matches:
        chunk_id = match.get("chunk_id")
        if not chunk_id or chunk_id in seen_chunk_ids:
            continue

        citations.append(
            {
                "chunk_id": chunk_id,
                "source_filename": match.get("source_filename", ""),
                "section_title": match.get("section_title", ""),
                "section_path": match.get("section_path", []),
                "heading_level": match.get("heading_level"),
            }
        )
        seen_chunk_ids.add(chunk_id)

        if len(citations) >= limit:
            break

    return citations


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
    answer_citations: list[dict] | None = None,
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
        "answer_citations": answer_citations or [],
    }


def generate_openai_answer(question: str, matches: list[dict], answer_started: float) -> dict:
    """Generate a RAG answer with OpenAI chat completions."""
    context_block = build_context_block(matches)
    answer_style = infer_answer_style(question, matches)
    payload = {
        "model": settings.openai_chat_model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": build_answer_instruction(answer_style),
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
            answer_citations=build_answer_citations(answer, matches),
        )
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        fallback_answer = build_fallback_answer(question, matches)
        return build_answer_result(
            answer=fallback_answer,
            answer_source="fallback_after_openai_error",
            chat_provider="fallback_after_openai_error",
            chat_model=settings.openai_chat_model,
            answer_started=answer_started,
            answer_citations=build_answer_citations(fallback_answer, matches),
        )


def generate_gemini_answer(question: str, matches: list[dict], answer_started: float) -> dict:
    """Generate a RAG answer with Gemini generateContent."""
    context_block = build_context_block(matches)
    answer_style = infer_answer_style(question, matches)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"{build_answer_instruction(answer_style)}\n\n"
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
            answer_citations=build_answer_citations(answer, matches),
        )
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        fallback_answer = build_fallback_answer(question, matches)
        return build_answer_result(
            answer=fallback_answer,
            answer_source="fallback_after_gemini_error",
            chat_provider="fallback_after_gemini_error",
            chat_model=settings.gemini_chat_model,
            answer_started=answer_started,
            answer_citations=build_answer_citations(fallback_answer, matches),
        )


def generate_rag_answer(question: str, matches: list[dict]) -> dict:
    """Generate a RAG answer from retrieved chunks."""
    answer_started = perf_counter()
    provider = settings.chat_provider.lower().strip()

    if provider == "fallback":
        fallback_answer = build_fallback_answer(question, matches)
        return build_answer_result(
            answer=fallback_answer,
            answer_source="fallback",
            chat_provider="fallback",
            chat_model="local-fallback",
            answer_started=answer_started,
            answer_citations=build_answer_citations(fallback_answer, matches),
        )

    if provider == "openai":
        if not settings.openai_api_key:
            fallback_answer = build_fallback_answer(question, matches)
            return build_answer_result(
                answer=fallback_answer,
                answer_source="fallback_missing_openai_key",
                chat_provider="fallback_missing_openai_key",
                chat_model=settings.openai_chat_model,
                answer_started=answer_started,
                answer_citations=build_answer_citations(fallback_answer, matches),
            )
        return generate_openai_answer(question, matches, answer_started)

    if provider == "gemini":
        if not settings.gemini_api_key:
            fallback_answer = build_fallback_answer(question, matches)
            return build_answer_result(
                answer=fallback_answer,
                answer_source="fallback_missing_gemini_key",
                chat_provider="fallback_missing_gemini_key",
                chat_model=settings.gemini_chat_model,
                answer_started=answer_started,
                answer_citations=build_answer_citations(fallback_answer, matches),
            )
        return generate_gemini_answer(question, matches, answer_started)

    fallback_answer = build_fallback_answer(question, matches)
    return build_answer_result(
        answer=fallback_answer,
        answer_source="fallback_unsupported_chat_provider",
        chat_provider="fallback_unsupported_chat_provider",
        chat_model="local-fallback",
        answer_started=answer_started,
        answer_citations=build_answer_citations(fallback_answer, matches),
    )
