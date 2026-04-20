from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ingestion.external_dataset_service import (  # noqa: E402
    list_external_dataset_targets,
    load_external_dataset_records,
    normalize_ticket_dataset_records,
    write_normalized_external_dataset,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize an external ticket or issue dataset into the project domain bundle format.",
    )
    parser.add_argument("--dataset", help="Dataset slug, for example bugsrepo_structured.")
    parser.add_argument("--input", help="Path to a local .json, .jsonl, or .csv export.")
    parser.add_argument("--limit", type=int, default=0, help="Optional record limit for smaller local tests.")
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="Print supported dataset targets and exit.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_datasets:
        print(json.dumps(list_external_dataset_targets(), ensure_ascii=False, indent=2))
        return 0

    if not args.dataset or not args.input:
        parser.error("--dataset and --input are required unless --list-datasets is used.")

    records = load_external_dataset_records(args.input)
    normalized_bundle = normalize_ticket_dataset_records(
        args.dataset,
        records,
        limit=args.limit if args.limit > 0 else None,
    )
    output_path = write_normalized_external_dataset(args.dataset, normalized_bundle)
    print(
        json.dumps(
            {
                "dataset": args.dataset,
                "input_path": str(Path(args.input).resolve()),
                "record_count": normalized_bundle["record_count"],
                "ticket_count": normalized_bundle["ticket_count"],
                "service_count": normalized_bundle["service_count"],
                "knowledge_asset_count": normalized_bundle["knowledge_asset_count"],
                "output_path": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
