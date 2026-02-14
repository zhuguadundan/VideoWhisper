import app.main as main


def test_test_connection_requires_provider(client):
    resp = client.post("/api/test-connection", json={"config": {}})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_test_connection_invalid_provider(client):
    resp = client.post(
        "/api/test-connection",
        json={"provider": "unknown", "config": {}},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_test_connection_siliconflow_success(client, monkeypatch):
    def fake_test(api_key, base_url, model):
        return True, "ok"

    monkeypatch.setattr(main, "_pt_test_siliconflow", fake_test)

    resp = client.post(
        "/api/test-connection",
        json={"provider": "siliconflow", "config": {"api_key": "k"}},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True


def test_test_connection_siliconflow_failure(client, monkeypatch):
    def fake_test(api_key, base_url, model):
        return False, "bad"

    monkeypatch.setattr(main, "_pt_test_siliconflow", fake_test)

    resp = client.post(
        "/api/test-connection",
        json={"provider": "siliconflow", "config": {"api_key": "k"}},
    )
    # ConnectionError propagated through api_error_handler -> 503
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["success"] is False


def test_test_connection_requires_admin_header_when_token_set(client, monkeypatch):
    """Backwards compatible: only enforced when ADMIN_TOKEN is configured."""

    monkeypatch.setenv("ADMIN_TOKEN", "t")

    resp = client.post(
        "/api/test-connection",
        json={"provider": "siliconflow", "config": {"api_key": "k"}},
    )
    assert resp.status_code == 403

    # Should proceed into handler (we stub siliconflow tester to avoid network)
    def fake_test(api_key, base_url, model):
        return True, "ok"

    monkeypatch.setattr(main, "_pt_test_siliconflow", fake_test)

    resp2 = client.post(
        "/api/test-connection",
        json={"provider": "siliconflow", "config": {"api_key": "k"}},
        headers={"X-Admin-Token": "t"},
    )
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2["success"] is True
