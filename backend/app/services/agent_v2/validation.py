def _normalize_question(question: str) -> str:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question_must_not_be_empty")
    return normalized_question


def _normalize_top_k(top_k: int) -> int:
    if top_k <= 0:
        raise ValueError("top_k_must_be_positive")
    return top_k
