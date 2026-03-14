from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.evaluation.retrieval_eval_service import evaluate_retrieval_dataset


def main() -> None:
    dataset_path = REPO_ROOT / "data" / "eval" / "rag_overview_retrieval_eval.json"
    report = evaluate_retrieval_dataset(dataset_path=dataset_path, top_k=3)

    print(f"Dataset: {dataset_path.name}")
    print(f"Top-k: {report.top_k}")
    print(f"Hit@{report.top_k}: {report.summary.hit_rate_at_k}")
    print(f"MRR: {report.summary.mean_reciprocal_rank}")

    for case in report.cases:
        print(
            f"{case.case_id}: hit={case.hit_at_k} rr={case.reciprocal_rank} "
            f"retrieved={case.retrieved_chunk_ids}"
        )


if __name__ == "__main__":
    main()
