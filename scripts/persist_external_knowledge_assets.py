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
    persist_imported_knowledge_assets,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist imported external knowledge assets into chunks, embeddings, and optionally Qdrant.",
    )
    parser.add_argument("--input", required=True, help="Path to a *.normalized.json bundle.")
    parser.add_argument("--limit", type=int, default=0, help="Optional processing limit.")
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Persist chunks only and skip embedding generation.",
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Persist embeddings without synchronizing them into Qdrant.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    result = persist_imported_knowledge_assets(
        args.input,
        limit=args.limit if args.limit > 0 else None,
        persist_embeddings=not args.skip_embeddings,
        sync_qdrant=not args.skip_qdrant,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
