"""Document search tool adapter — keyword and Qdrant semantic search."""

import uuid
from pathlib import Path
from typing import Any

from app.schemas.domain import KnowledgeAsset
from app.schemas.tools import ToolExecutionRequest, ToolExecutionResponse
from app.services.ingestion import document_service
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.retrieval.qdrant_retrieval_service import retrieve_with_qdrant_corpus

from app.services.agent.adapters._shared import (
    _build_tool_output_metadata,
    _infer_doc_kind,
    _parse_max_results_argument,
    _score_document_search_match,
)
from app.services.agent.adapters.registry import register_adapter


def _run_document_search_tool(request: ToolExecutionRequest) -> ToolExecutionResponse:
    query = request.target.strip()
    filename_filter = request.arguments.get("filename", "").strip()
    search_mode = request.arguments.get("search_mode", "").strip().lower()
    max_results = _parse_max_results_argument(request.arguments)
    trace_id = uuid.uuid4().hex

    if search_mode == "qdrant":
        source_prefixes = [
            item.strip()
            for item in request.arguments.get("source_prefixes", "").split(",")
            if item.strip()
        ]
        documents = document_service.list_documents()
        filenames = [
            item["filename"]
            for item in documents
            if not source_prefixes
            or any(item["filename"].startswith(prefix) for prefix in source_prefixes)
        ]
        retrieval = retrieve_with_qdrant_corpus(
            query,
            top_k=max_results or 3,
            filenames=filenames or None,
        )
        knowledge_assets = [
            KnowledgeAsset(
                doc_id=match.source_filename,
                service="",
                doc_kind=_infer_doc_kind(match.source_filename),
                section_path=[],
                tags=["external-evidence", "qdrant"],
                source_filename=match.source_filename,
                title=Path(match.source_filename).stem.replace("_", " ").replace("-", " ").strip(),
                snippet=match.content,
            ).model_dump(mode="json")
            for match in retrieval.matches
        ]
        matched_documents = [match.source_filename for match in retrieval.matches]
        output: dict[str, Any] = {
            **_build_tool_output_metadata(
                output_kind="search_results",
                resource_type="document_match",
                target=query,
                item_count=len(retrieval.matches),
            ),
            "query": query,
            "search_mode": "qdrant",
            "matched_count": str(len(retrieval.matches)),
            "returned_count": str(len(retrieval.matches)),
            "matched_documents": ", ".join(matched_documents),
            "skipped_documents": "0",
            "knowledge_assets": knowledge_assets,
            "max_results": str(max_results or 3),
            "retrieval_scope": retrieval.retrieval_scope,
            "query_embedding_model": retrieval.query_embedding_model,
        }
        if source_prefixes:
            output["source_prefixes"] = ", ".join(source_prefixes)
        if retrieval.matches:
            output["snippets"] = " | ".join(match.content[:240] for match in retrieval.matches[:3])
            output["top_match_document"] = retrieval.matches[0].source_filename
            output["top_match_score"] = f"{retrieval.matches[0].score:.3f}"
            output["top_match_reason"] = "qdrant semantic match"

        return ToolExecutionResponse(
            tool_name="document_search",
            action=request.action,
            target=query,
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=(
                f"Found {len(retrieval.matches)} Qdrant document match(es) for '{query}'."
                if retrieval.matches
                else f"No Qdrant documents matched '{query}'."
            ),
            trace_id=trace_id,
            executed_at=build_utc_timestamp(),
            output=output,
        )

    documents = document_service.list_documents()
    if filename_filter:
        documents = [item for item in documents if item["filename"] == filename_filter]

    ranked_matches: list[tuple[float, str, str, str]] = []
    skipped_documents = 0

    for item in documents:
        try:
            preview = document_service.read_text_document(item["filename"])
        except FileNotFoundError:
            continue
        except ValueError as exc:
            if str(exc) in {"unsupported_file_type", "text_decode_error"}:
                skipped_documents += 1
                continue
            raise

        content = preview["content"]
        lowered_content = content.lower()
        lowered_query = query.lower()

        if lowered_query not in lowered_content:
            continue

        first_index = lowered_content.index(lowered_query)
        score, snippet, reason = _score_document_search_match(
            filename=item["filename"],
            content=content,
            query=query,
            first_index=first_index,
        )
        ranked_matches.append((score, item["filename"], snippet, reason))

    ranked_matches.sort(key=lambda item: (-item[0], item[1]))
    returned_matches = ranked_matches[:max_results] if max_results else ranked_matches
    matched_documents = [filename for _, filename, _, _ in returned_matches]
    preview_snippets = [snippet for _, _, snippet, _ in returned_matches]
    knowledge_assets = [
        KnowledgeAsset(
            doc_id=filename,
            service="payment-service" if "payment" in filename.lower() else "",
            doc_kind=_infer_doc_kind(filename),
            section_path=[],
            tags=[_infer_doc_kind(filename)],
            source_filename=filename,
            title=Path(filename).stem.replace("_", " ").replace("-", " ").strip(),
            snippet=snippet,
        ).model_dump(mode="json")
        for _, filename, snippet, _ in returned_matches
    ]

    result_summary = (
        f"Found {len(matched_documents)} matching document(s) for '{query}'."
        if matched_documents
        else f"No documents matched '{query}'."
    )

    output: dict[str, Any] = {
        **_build_tool_output_metadata(
            output_kind="search_results",
            resource_type="document_match",
            target=query,
            item_count=len(returned_matches),
        ),
        "query": query,
        "matched_count": str(len(ranked_matches)),
        "returned_count": str(len(returned_matches)),
        "matched_documents": ", ".join(matched_documents),
        "skipped_documents": str(skipped_documents),
        "knowledge_assets": knowledge_assets,
    }
    if filename_filter:
        output["filename_filter"] = filename_filter
    if max_results:
        output["max_results"] = str(max_results)
    if preview_snippets:
        output["snippets"] = " | ".join(preview_snippets[:3])
    if ranked_matches:
        top_score, top_filename, _, top_reason = ranked_matches[0]
        output["top_match_document"] = top_filename
        output["top_match_score"] = f"{top_score:.3f}"
        output["top_match_reason"] = top_reason or "content match"

    return ToolExecutionResponse(
        tool_name="document_search",
        action=request.action,
        target=query,
        execution_status="completed",
        execution_mode="local_adapter",
        result_summary=result_summary,
        trace_id=trace_id,
        executed_at=build_utc_timestamp(),
        output=output,
    )


register_adapter("document_search", _run_document_search_tool)
