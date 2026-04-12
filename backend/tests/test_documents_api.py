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
            },
        },
    )

    response = client.get("/api/documents/rag_overview.md/assets")

    assert response.status_code == 200
    assert response.json()["knowledge_assets"] == {
        "chunks_ready": True,
        "embeddings_ready": True,
        "llamaindex_ready": False,
    }


def test_delete_document_endpoint_returns_404_for_missing_file():
    client = TestClient(app)

    response = client.delete("/api/documents/missing.md")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
