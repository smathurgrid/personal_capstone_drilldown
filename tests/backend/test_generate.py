"""Explainer generation API tests (mock provider)."""

from fastapi.testclient import TestClient


def test_generate_from_text_returns_image(client: TestClient) -> None:
    res = client.post(
        "/api/explainer/generate/generate-from-text",
        json={"topic": "smoke test turbine"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "image_b64" in body
    assert len(body["image_b64"]) > 0


def test_generate_from_text_requires_topic(client: TestClient) -> None:
    res = client.post("/api/explainer/generate/generate-from-text", json={"topic": ""})
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
