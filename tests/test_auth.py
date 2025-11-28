from flask import Flask, jsonify

import app.utils.auth as auth


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

