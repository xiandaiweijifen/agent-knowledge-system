"""Backfill persisted embedding artifacts into Qdrant."""

from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.vectorstore.qdrant_index_service import (  # noqa: E402
    sync_all_persisted_embeddings_to_qdrant,
)
from app.storage.vector.qdrant_client import close_qdrant_clients  # noqa: E402


def main() -> int:
    try:
        summary = sync_all_persisted_embeddings_to_qdrant()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["failed_count"] == 0 else 1
    finally:
        close_qdrant_clients()


if __name__ == "__main__":
    raise SystemExit(main())
