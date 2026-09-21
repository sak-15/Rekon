from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """
    Test root endpoint returns greeting and metadata.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Rekon" in data["message"]


def test_health_check():
    """
    Test health check endpoint returns status ok.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Rekon" in data["service"]
    assert "version" in data

