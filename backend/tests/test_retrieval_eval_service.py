import json

from app.services.evaluation.retrieval_eval_service import evaluate_retrieval_dataset
from app.services.indexing import embedding_service


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
