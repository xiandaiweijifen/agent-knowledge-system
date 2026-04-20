from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ingestion.external_knowledge_import_service import (  # noqa: E402
    import_normalized_knowledge_assets,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import normalized external knowledge assets into the local raw document store.",
    )
    parser.add_argument("--input", required=True, help="Path to a *.normalized.json bundle.")
    parser.add_argument("--limit", type=int, default=0, help="Optional import limit.")
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Replace existing imported raw documents instead of skipping them.",
    )
    parser.add_argument(
        "--persist-chunks",
        action="store_true",
        help="Immediately generate persisted chunks for imported documents.",
    )
    parser.add_argument(
        "--persist-embeddings",
        action="store_true",
        help="Immediately generate persisted embeddings for imported documents.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    result = import_normalized_knowledge_assets(
        args.input,
        limit=args.limit if args.limit > 0 else None,
        overwrite_existing=args.overwrite_existing,
        persist_chunks=args.persist_chunks,
        persist_embeddings=args.persist_embeddings,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
