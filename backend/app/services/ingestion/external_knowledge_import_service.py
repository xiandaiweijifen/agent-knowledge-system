from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.indexing.embedding_service import persist_document_embeddings
from app.services.ingestion.document_service import (
    get_document_asset_status,
    get_document_path,
    persist_document_chunks,
)
from app.services.vectorstore.qdrant_index_service import sync_document_embeddings_to_qdrant


def load_normalized_knowledge_bundle(input_path: str | Path) -> dict[str, Any]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Normalized external knowledge bundle not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("normalized_external_bundle_must_be_object")

    knowledge_assets = payload.get("knowledge_assets")
    if not isinstance(knowledge_assets, list):
        raise ValueError("normalized_external_bundle_missing_knowledge_assets")

    return payload


def _render_knowledge_asset_markdown(asset: dict[str, Any], dataset_slug: str) -> str:
    title = str(asset.get("title") or asset.get("doc_id") or "Imported Knowledge Asset").strip()
    service = str(asset.get("service") or "unknown-service").strip()
    doc_kind = str(asset.get("doc_kind") or "reference").strip()
    tags = [str(tag).strip() for tag in asset.get("tags", []) if str(tag).strip()]
    snippet = str(asset.get("snippet") or "").strip()
    source_filename = str(asset.get("source_filename") or "").strip()
    doc_id = str(asset.get("doc_id") or "").strip()

    lines = [
        f"# {title}",
        "",
        f"- Dataset: {dataset_slug}",
        f"- Doc ID: {doc_id or 'unknown'}",
        f"- Service: {service or 'unknown-service'}",
        f"- Document Kind: {doc_kind or 'reference'}",
        f"- Source Filename: {source_filename or 'unknown'}",
    ]
    if tags:
        lines.append(f"- Tags: {', '.join(tags)}")
    lines.extend(
        [
            "",
            "## Imported Snippet",
            "",
            snippet or "No snippet available.",
            "",
        ]
    )
    return "\n".join(lines)


def import_normalized_knowledge_assets(
    input_path: str | Path,
    *,
    limit: int | None = None,
    overwrite_existing: bool = False,
    persist_chunks: bool = False,
    persist_embeddings: bool = False,
) -> dict[str, Any]:
    bundle = load_normalized_knowledge_bundle(input_path)
    dataset = bundle.get("dataset", {})
    dataset_slug = str(dataset.get("slug") or "external_dataset").strip() or "external_dataset"

    raw_assets = bundle.get("knowledge_assets", [])
    selected_assets = raw_assets[:limit] if limit and limit > 0 else raw_assets

    imported_count = 0
    overwritten_count = 0
    skipped_count = 0
    chunked_count = 0
    embedded_count = 0
    imported_filenames: list[str] = []

    for asset in selected_assets:
        filename = str(asset.get("source_filename") or "").strip()
        if not filename:
            skipped_count += 1
            continue

        destination = get_document_path(filename)
        existed_before = destination.exists()
        if existed_before and not overwrite_existing:
            skipped_count += 1
            continue

        markdown = _render_knowledge_asset_markdown(asset, dataset_slug)
        destination.write_text(markdown, encoding="utf-8")
        imported_filenames.append(filename)

        if existed_before and overwrite_existing:
            overwritten_count += 1
        else:
            imported_count += 1

        if persist_chunks:
            persist_document_chunks(filename)
            chunked_count += 1

        if persist_embeddings:
            persist_document_embeddings(filename)
            embedded_count += 1

    return {
        "dataset": dataset_slug,
        "input_path": str(Path(input_path).resolve()),
        "selected_asset_count": len(selected_assets),
        "imported_count": imported_count,
        "overwritten_count": overwritten_count,
        "skipped_count": skipped_count,
        "chunked_count": chunked_count,
        "embedded_count": embedded_count,
        "filenames": imported_filenames,
    }


def persist_imported_knowledge_assets(
    input_path: str | Path,
    *,
    limit: int | None = None,
    persist_embeddings: bool = True,
    sync_qdrant: bool = True,
) -> dict[str, Any]:
    bundle = load_normalized_knowledge_bundle(input_path)
    dataset = bundle.get("dataset", {})
    dataset_slug = str(dataset.get("slug") or "external_dataset").strip() or "external_dataset"

    raw_assets = bundle.get("knowledge_assets", [])
    selected_assets = raw_assets[:limit] if limit and limit > 0 else raw_assets

    persisted_count = 0
    embedded_count = 0
    qdrant_synced_count = 0
    skipped_count = 0
    results: list[dict[str, Any]] = []

    for asset in selected_assets:
        filename = str(asset.get("source_filename") or "").strip()
        if not filename:
            skipped_count += 1
            continue

        document_path = get_document_path(filename)
        if not document_path.exists():
            skipped_count += 1
            results.append(
                {
                    "filename": filename,
                    "chunked": False,
                    "embedded": False,
                    "qdrant_synced": False,
                    "warning": "raw_document_missing",
                }
            )
            continue

        persist_document_chunks(filename)
        persisted_count += 1

        embedded = False
        qdrant_synced = False
        warning: str | None = None

        if persist_embeddings:
            persist_document_embeddings(filename)
            embedded = True
            embedded_count += 1

        if persist_embeddings and sync_qdrant:
            try:
                qdrant_result = sync_document_embeddings_to_qdrant(filename)
                qdrant_synced = bool(qdrant_result.get("synced"))
                if qdrant_synced:
                    qdrant_synced_count += 1
                elif qdrant_result.get("reason"):
                    warning = str(qdrant_result["reason"])
            except Exception as exc:
                warning = str(exc)

        results.append(
            {
                "filename": filename,
                "chunked": True,
                "embedded": embedded,
                "qdrant_synced": qdrant_synced,
                "knowledge_assets": get_document_asset_status(filename).get("knowledge_assets", {}),
                "warning": warning,
            }
        )

    return {
        "dataset": dataset_slug,
        "input_path": str(Path(input_path).resolve()),
        "selected_asset_count": len(selected_assets),
        "chunked_count": persisted_count,
        "embedded_count": embedded_count,
        "qdrant_synced_count": qdrant_synced_count,
        "skipped_count": skipped_count,
        "results": results,
    }
