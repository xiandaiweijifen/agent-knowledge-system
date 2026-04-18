import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.evaluation import report_store_service, retrieval_eval_service
from app.storage.vector.qdrant_client import close_qdrant_clients


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval evaluation datasets.")
    parser.add_argument(
        "--dataset",
        action="append",
        dest="datasets",
        help="Specific dataset name under data/eval. Can be passed multiple times.",
    )
    parser.add_argument(
        "--all-datasets",
        action="store_true",
        help="Evaluate every *_retrieval_eval.json dataset.",
    )
    parser.add_argument(
        "--provider",
        action="append",
        dest="providers",
        help="Vector store provider to evaluate, e.g. qdrant or llamaindex. Can be repeated.",
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist each retrieval report into tool_state/evaluation_reports.",
    )
    return parser.parse_args()


def _resolved_dataset_names(args: argparse.Namespace) -> list[str]:
    if args.all_datasets:
        return [dataset.dataset_name for dataset in retrieval_eval_service.list_retrieval_datasets()]

    if args.datasets:
        return args.datasets

    return ["rag_overview_retrieval_eval.json"]


def _resolved_providers(args: argparse.Namespace) -> list[str | None]:
    if not args.providers:
        return [None]
    return args.providers


def main() -> None:
    args = _parse_args()
    datasets = _resolved_dataset_names(args)
    providers = _resolved_providers(args)
    results: list[dict[str, object]] = []

    try:
        for provider in providers:
            provider_label = provider or "active_config"
            provider_results: list[dict[str, object]] = []
            failed_results: list[dict[str, object]] = []
            for dataset_name in datasets:
                try:
                    report = retrieval_eval_service.evaluate_named_retrieval_dataset(
                        dataset_name=dataset_name,
                        top_k=args.top_k,
                        vector_store_provider=provider,
                    )
                    if args.persist:
                        report_store_service.persist_retrieval_report(
                            dataset_name=dataset_name,
                            top_k=args.top_k,
                            report=report,
                            vector_store_provider=provider,
                        )

                    provider_results.append(
                        {
                            "dataset_name": dataset_name,
                            "top_k": report.top_k,
                            "vector_store_provider": report.vector_store_provider,
                            "hit_rate_at_k": report.summary.hit_rate_at_k,
                            "mean_reciprocal_rank": report.summary.mean_reciprocal_rank,
                            "grounded_case_rate": report.summary.grounded_case_rate,
                            "mean_citation_coverage": report.summary.mean_citation_coverage,
                            "mean_retrieval_latency_ms": report.summary.mean_retrieval_latency_ms,
                            "mean_answer_latency_ms": report.summary.mean_answer_latency_ms,
                        }
                    )
                except Exception as exc:
                    failed_results.append(
                        {
                            "dataset_name": dataset_name,
                            "vector_store_provider": provider_label,
                            "error": str(exc),
                        }
                    )

            dataset_count = len(provider_results)
            results.append(
                {
                    "provider": provider_label,
                    "dataset_count": dataset_count,
                    "failed_count": len(failed_results),
                    "top_k": args.top_k,
                    "persisted": bool(args.persist),
                    "datasets": provider_results,
                    "failures": failed_results,
                    "mean_hit_rate_at_k": round(
                        sum(item["hit_rate_at_k"] for item in provider_results) / dataset_count,
                        6,
                    )
                    if dataset_count
                    else 0.0,
                    "mean_reciprocal_rank": round(
                        sum(item["mean_reciprocal_rank"] for item in provider_results) / dataset_count,
                        6,
                    )
                    if dataset_count
                    else 0.0,
                    "mean_retrieval_latency_ms": round(
                        sum(item["mean_retrieval_latency_ms"] for item in provider_results) / dataset_count,
                        3,
                    )
                    if dataset_count
                    else 0.0,
                }
            )
    finally:
        close_qdrant_clients()

    print(json.dumps({"runs": results}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
