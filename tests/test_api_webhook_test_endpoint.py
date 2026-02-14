def test_webhook_test_requires_admin_header_when_token_set(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "t")

    # Avoid outbound HTTP
    monkeypatch.setattr(
        "app.utils.webhook_notifier.send_task_completed_webhooks",
        lambda *args, **kwargs: None,
    )

    resp = client.post(
        "/api/webhook/test",
        json={
            "webhook": {
                "enabled": True,
                "bark": {"enabled": True, "server": "https://api.day.app", "key": "k"},
            }
        },
    )
    assert resp.status_code == 403

    resp2 = client.post(
        "/api/webhook/test",
        headers={"X-Admin-Token": "t"},
        json={
            "webhook": {
                "enabled": True,
                "bark": {"enabled": True, "server": "https://api.day.app", "key": "k"},
            }
        },
    )
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2["success"] is True


def test_webhook_test_strict_mode_rejects_private_or_http_targets(client, monkeypatch):
    # Strict mode is opt-in.
    monkeypatch.setenv("ENFORCE_WEBHOOK_URL_SAFETY", "true")

    # Avoid outbound HTTP if validation accidentally passes
    monkeypatch.setattr(
        "app.utils.webhook_notifier.send_task_completed_webhooks",
        lambda *args, **kwargs: None,
    )

    resp = client.post(
        "/api/webhook/test",
        json={
            "webhook": {
                "enabled": True,
                "bark": {
                    "enabled": True,
                    "server": "http://127.0.0.1:1234",
                    "key": "k",
                },
                "wecom": {"enabled": True, "webhook_url": "http://127.0.0.1:5678"},
            }
        },
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
