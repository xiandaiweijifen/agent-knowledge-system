from fastapi.testclient import TestClient

from app.main import app


def test_delete_document_endpoint_returns_404_for_missing_file():
    client = TestClient(app)

    response = client.delete("/api/documents/missing.md")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
