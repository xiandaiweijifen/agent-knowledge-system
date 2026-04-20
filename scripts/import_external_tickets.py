from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ingestion.external_ticket_import_service import (  # noqa: E402
    import_normalized_tickets_to_store,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import normalized external incident tickets into the local ticket store.",
    )
    parser.add_argument("--input", required=True, help="Path to a *.normalized.json bundle.")
    parser.add_argument("--limit", type=int, default=0, help="Optional import limit.")
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Replace existing ticket ids instead of skipping them.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    result = import_normalized_tickets_to_store(
        args.input,
        limit=args.limit if args.limit > 0 else None,
        overwrite_existing=args.overwrite_existing,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
