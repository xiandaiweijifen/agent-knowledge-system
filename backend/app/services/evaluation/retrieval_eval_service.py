import json
from pathlib import Path

from app.core.config import DATA_ROOT
from app.schemas.evaluation_api import RetrievalEvalDatasetInfo
from app.schemas.evaluation import (
    RetrievalEvalCase,
    RetrievalEvalCaseResult,
    RetrievalEvalReport,
    RetrievalEvalSummary,
)
from app.services.retrieval.retrieval_service import retrieve_relevant_chunks

EVAL_DATA_DIR = DATA_ROOT / "eval"


def load_retrieval_eval_cases(dataset_path: Path) -> list[RetrievalEvalCase]:
    """Load retrieval evaluation cases from a JSON dataset."""
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [RetrievalEvalCase.model_validate(item) for item in payload["cases"]]


def compute_reciprocal_rank(
    expected_chunk_ids: list[str],
    retrieved_chunk_ids: list[str],
) -> float:
    """Compute reciprocal rank for a retrieval result."""
    expected_set = set(expected_chunk_ids)

    for index, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in expected_set:
            return round(1 / index, 6)

    return 0.0


def evaluate_retrieval_dataset(dataset_path: Path, top_k: int = 3) -> RetrievalEvalReport:
    """Evaluate retrieval performance on a local dataset."""
    cases = load_retrieval_eval_cases(dataset_path)
    case_results = []

    for case in cases:
        retrieval_result = retrieve_relevant_chunks(
            filename=case.filename,
            query_text=case.question,
            top_k=top_k,
        )
        retrieved_chunk_ids = [match.chunk_id for match in retrieval_result.matches]
        expected_set = set(case.expected_chunk_ids)
        hit_at_k = any(chunk_id in expected_set for chunk_id in retrieved_chunk_ids)
        reciprocal_rank = compute_reciprocal_rank(
            expected_chunk_ids=case.expected_chunk_ids,
            retrieved_chunk_ids=retrieved_chunk_ids,
        )

        case_results.append(
            RetrievalEvalCaseResult(
                case_id=case.case_id,
                filename=case.filename,
                question=case.question,
                expected_chunk_ids=case.expected_chunk_ids,
                retrieved_chunk_ids=retrieved_chunk_ids,
                hit_at_k=hit_at_k,
                reciprocal_rank=reciprocal_rank,
            )
        )

    total_cases = len(case_results)
    hit_count = sum(1 for result in case_results if result.hit_at_k)
    reciprocal_rank_sum = sum(result.reciprocal_rank for result in case_results)

    summary = RetrievalEvalSummary(
        total_cases=total_cases,
        hit_rate_at_k=round(hit_count / total_cases, 6) if total_cases else 0.0,
        mean_reciprocal_rank=round(reciprocal_rank_sum / total_cases, 6)
        if total_cases
        else 0.0,
    )

    return RetrievalEvalReport(
        top_k=top_k,
        summary=summary,
        cases=case_results,
    )


def evaluate_named_retrieval_dataset(dataset_name: str, top_k: int = 3) -> RetrievalEvalReport:
    """Evaluate retrieval performance for a named local dataset."""
    if top_k <= 0:
        raise ValueError("top_k_must_be_positive")

    normalized_name = dataset_name.strip()

    if not normalized_name:
        raise ValueError("dataset_name_must_not_be_empty")

    dataset_path = EVAL_DATA_DIR / normalized_name

    if not dataset_path.exists() or not dataset_path.is_file():
        raise FileNotFoundError(dataset_name)

    return evaluate_retrieval_dataset(dataset_path=dataset_path, top_k=top_k)


def list_retrieval_datasets() -> list[RetrievalEvalDatasetInfo]:
    """List available retrieval evaluation datasets."""
    datasets = []

    if not EVAL_DATA_DIR.exists():
        return datasets

    for dataset_path in sorted(EVAL_DATA_DIR.glob("*_retrieval_eval.json")):
        cases = load_retrieval_eval_cases(dataset_path)
        filenames = sorted({case.filename for case in cases})

        datasets.append(
            RetrievalEvalDatasetInfo(
                dataset_name=dataset_path.name,
                case_count=len(cases),
                filenames=filenames,
            )
        )

    return datasets
