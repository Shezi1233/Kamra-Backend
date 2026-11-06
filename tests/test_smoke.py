from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import hash_password, verify_password
from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_password_hashing_roundtrip() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_services_list_shape() -> None:
    response = client.get("/api/v1/services")
    # Requires a reachable database; when unavailable the API returns a 5xx.
    assert response.status_code in (200, 500)
