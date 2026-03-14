from fastapi.testclient import TestClient

from app.main import app


def test_system_health_endpoint_returns_provider_summary():
    client = TestClient(app)

    response = client.get("/api/health/system")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "embedding_provider" in payload
    assert "chat_provider" in payload
    assert "providers" in payload
    assert "storage" in payload
    assert "gemini_configured" in payload["providers"]
    assert "openai_configured" in payload["providers"]
