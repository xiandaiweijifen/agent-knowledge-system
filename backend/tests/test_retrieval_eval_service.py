import json

from app.services.evaluation import retrieval_eval_service
from app.services.evaluation.retrieval_eval_service import (
    evaluate_retrieval_dataset,
    list_retrieval_datasets,
)
from app.services.indexing import embedding_service
from app.services.retrieval.retrieval_service import compute_rerank_bonus


def test_evaluate_retrieval_dataset_computes_hit_rate_and_mrr(
    workspace_tmp_path,
    monkeypatch,
):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()
    dataset_path = workspace_tmp_path / "eval.json"

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)

    embedding_payload = {
        "filename": "sample.txt",
        "suffix": ".txt",
        "embedding_provider": "mock",
        "embedding_model": "mock-embedding-v1",
        "vector_dim": 8,
        "source_path": "../data/raw/sample.txt",
        "source_chunk_path": "../data/chunks/sample.chunks.json",
        "created_at": "2026-03-14T00:00:00+00:00",
        "pipeline_version": "indexing-v1",
        "chunk_count": 2,
        "embeddings": [
            {
                "embedding_id": "sample.txt::chunk_0::embedding",
                "chunk_id": "sample.txt::chunk_0",
                "chunk_index": 0,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "char_count": 11,
                "content": "rag systems",
                "vector": embedding_service.build_mock_embedding("rag systems"),
            },
            {
                "embedding_id": "sample.txt::chunk_1::embedding",
                "chunk_id": "sample.txt::chunk_1",
                "chunk_index": 1,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "char_count": 12,
                "content": "agent system",
                "vector": embedding_service.build_mock_embedding("agent system"),
            },
        ],
    }
    (embedding_dir / "sample.embeddings.json").write_text(
        json.dumps(embedding_payload),
        encoding="utf-8",
    )
    dataset_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_1",
                        "filename": "sample.txt",
                        "question": "rag systems",
                        "expected_chunk_ids": ["sample.txt::chunk_0"],
                    },
                    {
                        "case_id": "case_2",
                        "filename": "sample.txt",
                        "question": "agent system",
                        "expected_chunk_ids": ["sample.txt::chunk_1"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_retrieval_dataset(dataset_path=dataset_path, top_k=1)

    assert report.summary.total_cases == 2
    assert report.summary.hit_rate_at_k == 1.0
    assert report.summary.mean_reciprocal_rank == 1.0
    assert all(case.hit_at_k for case in report.cases)


def test_list_retrieval_datasets_only_includes_retrieval_eval_files(
    workspace_tmp_path,
    monkeypatch,
):
    eval_dir = workspace_tmp_path / "eval"
    eval_dir.mkdir()

    (eval_dir / "rag_overview_retrieval_eval.json").write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_1",
                        "filename": "rag_overview.md",
                        "question": "What is RAG?",
                        "expected_chunk_ids": ["rag_overview.md::chunk_0"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (eval_dir / "agent_route_eval.json").write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "route_1",
                        "question": "Create a ticket",
                        "expected_route_type": "tool_execution",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(retrieval_eval_service, "EVAL_DATA_DIR", eval_dir)

    datasets = list_retrieval_datasets()

    assert len(datasets) == 1
    assert datasets[0].dataset_name == "rag_overview_retrieval_eval.json"


def test_rerank_bonus_prefers_exact_workflow_path_phrase():
    query = "When should the agent use the tool execution path?"
    tool_execution_chunk = """
If the request requires action, the workflow should move into a tool execution
path. The agent may call a ticketing tool, a deployment tool, a search API, or
an internal service.
    """.strip()
    routing_chunk = """
The first step in an agent workflow is request routing. A router examines the
user question and decides which path should handle it. Some requests are
execution requests that require tools.
    """.strip()

    assert compute_rerank_bonus(query, tool_execution_chunk) > compute_rerank_bonus(
        query,
        routing_chunk,
    )


def test_rerank_bonus_prefers_observability_anchor_terms():
    query = "What should engineers log for observability in an agent workflow system?"
    observability_chunk = """
Observability is critical in an agent workflow system. Engineers should log the
route decision, retrieval latency, tool latency, answer latency, provider
selection, fallback behavior, and final action status.
    """.strip()
    routing_chunk = """
The first step in an agent workflow is request routing. A router examines the
user question and decides which path should handle it.
    """.strip()

    assert compute_rerank_bonus(query, observability_chunk) > compute_rerank_bonus(
        query,
        routing_chunk,
    )
