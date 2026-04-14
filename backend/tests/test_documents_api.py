from fastapi.testclient import TestClient

from app.main import app


def test_get_document_assets_returns_readiness(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "app.api.routes.documents.get_document_asset_status",
        lambda filename: {
            "filename": filename,
            "size_bytes": 128,
            "suffix": ".md",
            "knowledge_assets": {
                "chunks_ready": True,
                "embeddings_ready": True,
                "llamaindex_ready": False,
                "qdrant_ready": True,
            },
        },
    )

    response = client.get("/api/documents/rag_overview.md/assets")

    assert response.status_code == 200
    assert response.json()["knowledge_assets"] == {
        "chunks_ready": True,
        "embeddings_ready": True,
        "llamaindex_ready": False,
        "qdrant_ready": True,
    }


def test_delete_document_endpoint_returns_404_for_missing_file():
    client = TestClient(app)

    response = client.delete("/api/documents/missing.md")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_persist_embeddings_endpoint_includes_qdrant_sync_summary(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "app.api.routes.documents.persist_document_embeddings",
        lambda filename: {
            "filename": filename,
            "embedding_provider": "mock",
            "embedding_model": "mock-embedding-v1",
            "vector_dim": 8,
            "embedding_count": 2,
            "created_at": "2026-04-14T00:00:00+00:00",
            "pipeline_version": "indexing-v1",
        },
    )
    monkeypatch.setattr(
        "app.api.routes.documents.sync_document_embeddings_to_qdrant",
        lambda filename: {
            "enabled": True,
            "synced": True,
            "collection_name": "agent_knowledge_chunks",
            "point_count": 2,
        },
    )
    monkeypatch.setattr(
        "app.api.routes.documents.build_vector_index",
        lambda filename: {
            "filename": filename,
            "node_count": 2,
            "store_path": "data/llamaindex_store/sample",
        },
    )

    response = client.post("/api/documents/sample.txt/embeddings/persist")

    assert response.status_code == 200
    payload = response.json()
    assert payload["qdrant_point_count"] == 2
    assert payload["qdrant_collection_name"] == "agent_knowledge_chunks"
    assert payload["llamaindex_node_count"] == 2
