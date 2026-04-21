from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.retrieval.qdrant_retrieval_service import retrieve_with_qdrant_corpus  # noqa: E402
from app.storage.vector.qdrant_client import build_qdrant_client, get_qdrant_collection_name  # noqa: E402


@dataclass(frozen=True)
class RetrievalSmokeCase:
    name: str
    query: str
    expected_filename_prefix: str


SMOKE_CASES = (
    RetrievalSmokeCase(
        name="customer_support_security_incident",
        query="wesentlicher sicherheitsvorfall cloud plattformen datenverletzung",
        expected_filename_prefix="customer_support_tickets_",
    ),
    RetrievalSmokeCase(
        name="it_support_outlook_exchange",
        query="outlook exchange large attachments",
        expected_filename_prefix="it_support_v2_",
    ),
    RetrievalSmokeCase(
        name="bugsrepo_filesystem_tracking_bug",
        query="filesystem sync access handle tracking bug",
        expected_filename_prefix="bugsrepo_structured_",
    ),
)


def _collection_summary() -> dict[str, Any]:
    client = build_qdrant_client()
    if client is None:
        return {"available": False, "reason": "qdrant_not_configured"}

    info = client.get_collection(get_qdrant_collection_name())
    return {
        "available": True,
        "collection_name": get_qdrant_collection_name(),
        "points_count": info.points_count,
        "vector_size": info.config.params.vectors.size,
        "status": str(info.status),
    }


def run_smoke_cases(*, top_k: int) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    for case in SMOKE_CASES:
        retrieval = retrieve_with_qdrant_corpus(case.query, top_k=top_k)
        matches = [
            {
                "source_filename": match.source_filename,
                "score": match.score,
                "snippet": match.content[:240].replace("\n", " "),
            }
            for match in retrieval.matches
        ]
        expected_hit = any(
            match["source_filename"].startswith(case.expected_filename_prefix)
            for match in matches
        )
        results.append(
            {
                "name": case.name,
                "query": case.query,
                "expected_filename_prefix": case.expected_filename_prefix,
                "expected_hit": expected_hit,
                "match_count": len(matches),
                "matches": matches,
            }
        )

    return {
        "collection": _collection_summary(),
        "top_k": top_k,
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result["expected_hit"]),
        "failed_count": sum(1 for result in results if not result["expected_hit"]),
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate that imported external knowledge can be retrieved from Qdrant.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of matches to inspect per query.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any smoke case does not hit its expected source prefix.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_smoke_cases(top_k=args.top_k)
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if args.strict and summary["failed_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
