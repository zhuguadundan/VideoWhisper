import app.main as main


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"].startswith("v")
    assert isinstance(data.get("features"), list)


def test_providers_endpoint_uses_text_processor(client, monkeypatch):
    providers = [{"id": "p1", "name": "Provider 1"}]

    monkeypatch.setattr(
        main.video_processor.text_processor,
        "get_available_providers",
        lambda: providers,
    )
    monkeypatch.setattr(
        main.video_processor.text_processor,
        "get_default_provider",
        lambda: "p1",
    )

    resp = client.get("/api/providers")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "data" in data
    assert data["data"]["providers"] == providers
    assert data["data"]["default"] == "p1"

