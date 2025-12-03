from flask import Flask, jsonify

import app.utils.auth as auth
import app.config.settings as settings
from app.config.settings import Config


def _make_app_with_protected_route():
    app = Flask(__name__)

    @app.route("/protected")
    @auth.admin_protected
    def protected():  # pragma: no cover - inner logic tested via wrapper
        return jsonify({"ok": True})

    # Reset module-level warning flag between tests
    auth._warned_no_admin = False
    return app


def test_admin_protected_allows_without_token_in_dev(monkeypatch):
    """In development with no ADMIN_TOKEN, route should be open."""

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("ENFORCE_ADMIN_TOKEN", raising=False)

    app = _make_app_with_protected_route()
    client = app.test_client()

    resp = client.get("/protected")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_admin_protected_requires_header_when_token_set(monkeypatch):
    """When ADMIN_TOKEN is set, valid X-Admin-Token is required."""

    monkeypatch.setenv("ADMIN_TOKEN", "secret123")
    monkeypatch.setenv("FLASK_ENV", "production")

    app = _make_app_with_protected_route()
    client = app.test_client()

    # Missing header -> 403
    resp = client.get("/protected")
    assert resp.status_code == 403

    # Correct header -> 200
    resp2 = client.get("/protected", headers={"X-Admin-Token": "secret123"})
    assert resp2.status_code == 200
    assert resp2.get_json()["ok"] is True


def test_admin_protected_enforced_in_production_without_token(monkeypatch):
    """Production + ENFORCE_ADMIN_TOKEN=true + no token should be rejected."""

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ENFORCE_ADMIN_TOKEN", "true")

    app = _make_app_with_protected_route()
    client = app.test_client()

    resp = client.get("/protected")
    assert resp.status_code == 403


def test_admin_protected_enforced_via_config_security_flag(monkeypatch):
    """Production + security.enforce_admin_token=true should be rejected without token."""

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("ENFORCE_ADMIN_TOKEN", raising=False)

    def fake_load_config():
        return {"security": {"enforce_admin_token": True}}

    # Ensure Config.load_config reads our in-memory security config
    monkeypatch.setattr(Config, "load_config", staticmethod(fake_load_config))

    app = _make_app_with_protected_route()
    client = app.test_client()

    resp = client.get("/protected")
    assert resp.status_code == 403


def test_admin_protected_logs_warning_once_in_production_without_enforcement(monkeypatch, caplog):
    """Production + no token + no enforcement should log once then allow access."""

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("ENFORCE_ADMIN_TOKEN", raising=False)

    # Config without enforce_admin_token
    def fake_load_config():
        return {"security": {"enforce_admin_token": False}}

    monkeypatch.setattr(Config, "load_config", staticmethod(fake_load_config))

    app = _make_app_with_protected_route()
    client = app.test_client()

    # First request should log a warning and allow access
    with caplog.at_level("WARNING"):
        resp1 = client.get("/protected")
        resp2 = client.get("/protected")

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    warn_messages = [
        r.getMessage()
        for r in caplog.records
        if "生产环境未配置 ADMIN_TOKEN" in r.getMessage()
    ]
    # Only one warning should be emitted despite two requests
    assert len(warn_messages) == 1
