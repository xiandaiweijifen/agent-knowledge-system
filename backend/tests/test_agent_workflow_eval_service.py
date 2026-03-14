import json

from app.services.evaluation.agent_workflow_eval_service import evaluate_agent_workflow_dataset
from app.services.indexing import embedding_service
from app.core.config import settings


def test_evaluate_agent_workflow_dataset_computes_workflow_accuracy(
    workspace_tmp_path,
    monkeypatch,
):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()
    dataset_path = workspace_tmp_path / "agent_workflow_eval.json"

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "chat_provider", "fallback")

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
        "chunk_count": 1,
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
            }
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
                        "question": "What are rag systems?",
                        "filename": "sample.txt",
                        "top_k": 1,
                        "expected_route_type": "knowledge_retrieval",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_2",
                        "question": "Create a ticket for the payment service outage",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_3",
                        "question": "Please do that for production",
                        "expected_route_type": "clarification_needed",
                        "expected_workflow_status": "clarification_required",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_agent_workflow_dataset(dataset_path=dataset_path)

    assert report.summary.total_cases == 3
    assert report.summary.workflow_accuracy == 1.0
    assert all(case.matched for case in report.cases)
