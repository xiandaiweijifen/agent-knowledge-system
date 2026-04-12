import json
from types import SimpleNamespace

from app.services.evaluation import retrieval_eval_service
from app.services.evaluation.retrieval_eval_service import (
    evaluate_retrieval_dataset,
    list_retrieval_datasets,
)
from app.services.retrieval.retrieval_service import (
    compute_rerank_bonus,
    normalize_query_text,
)


def test_evaluate_retrieval_dataset_computes_hit_rate_and_mrr(
    workspace_tmp_path,
    monkeypatch,
):
    dataset_path = workspace_tmp_path / "eval.json"
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

    query_results = {
        "rag systems": SimpleNamespace(
            retrieval=SimpleNamespace(
                matches=[SimpleNamespace(chunk_id="sample.txt::chunk_0", document_kind="overview")]
            ),
            answer_verification=SimpleNamespace(
                groundedness_status="grounded",
                citation_coverage=1.0,
            ),
            answer_citations=[SimpleNamespace(document_kind="overview")],
        ),
        "agent system": SimpleNamespace(
            retrieval=SimpleNamespace(
                matches=[SimpleNamespace(chunk_id="sample.txt::chunk_1", document_kind="workflow")]
            ),
            answer_verification=SimpleNamespace(
                groundedness_status="partially_grounded",
                citation_coverage=0.5,
            ),
            answer_citations=[
                SimpleNamespace(document_kind="workflow"),
                SimpleNamespace(document_kind="reference"),
            ],
        ),
    }

    monkeypatch.setattr(
        retrieval_eval_service,
        "run_query_with_context",
        lambda filename, question, top_k, execution_context: query_results[question],
    )

    report = evaluate_retrieval_dataset(dataset_path=dataset_path, top_k=1)

    assert report.summary.total_cases == 2
    assert report.summary.hit_rate_at_k == 1.0
    assert report.summary.mean_reciprocal_rank == 1.0
    assert report.summary.grounded_case_rate == 0.5
    assert report.summary.mean_citation_coverage == 0.75
    assert all(case.hit_at_k for case in report.cases)
    assert report.cases[0].groundedness_status == "grounded"
    assert report.cases[1].citation_coverage == 0.5
    assert report.cases[0].top_document_kind == "overview"
    assert report.cases[1].citation_document_kinds == ["reference", "workflow"]


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


def test_normalize_query_text_strips_polite_prefixes():
    query = "Can you explain retrieval-augmented generation?"

    assert normalize_query_text(query) == "explain retrieval-augmented generation?"


def test_rerank_bonus_prefers_matching_section_metadata():
    query = "What are the common failure modes in rag systems?"
    generic_chunk = "This chunk discusses generic platform architecture details."

    assert compute_rerank_bonus(
        query,
        generic_chunk,
        section_title="Common Failure Modes",
        section_path=["Retrieval-Augmented Generation Overview", "Common Failure Modes"],
    ) > compute_rerank_bonus(
        query,
        generic_chunk,
        section_title="Platform Overview",
        section_path=["Platform Overview"],
    )
