"""API health endpoint regression tests."""

from fastapi.testclient import TestClient


def test_root_lists_modes(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code == 200
    body = res.json()
    assert body["health"] == "/api/health"
    assert "ecommerce" in body["modes"]
    assert "explainer_vision" in body["modes"]


def test_global_health_ok(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "ecommerce" in body["modules"]
    assert "explainer_vision" in body["modules"]
    assert "explainer_generate" in body["modules"]


def test_module_health_endpoints(client: TestClient) -> None:
    for path in (
        "/api/ecommerce/health",
        "/api/explainer/vision/health",
        "/api/explainer/generate/health",
    ):
        res = client.get(path)
        assert res.status_code == 200, path
        assert res.json()["status"] == "ok", path
