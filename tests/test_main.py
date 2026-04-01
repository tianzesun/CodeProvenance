"""
Basic tests for IntegrityDesk main application.
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Welcome to IntegrityDesk API" in data["message"]


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_api_docs_available():
    """Test that API documentation is available."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_redoc_available():
    """Test that ReDoc documentation is available."""
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_json():
    """Test that OpenAPI JSON schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert data["info"]["title"] == "IntegrityDesk"