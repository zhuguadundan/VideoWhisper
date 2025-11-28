from flask import Flask, jsonify, g

from app.utils.error_handler import api_error_handler, safe_json_response


def _create_error_app():
    app = Flask(__name__)

    @app.route("/err/value")
    @api_error_handler
    def err_value():  # pragma: no cover - tested via wrapper
        raise ValueError("bad param")

    @app.route("/err/notfound")
    @api_error_handler
    def err_notfound():  # pragma: no cover
        raise FileNotFoundError("missing file")

    @app.route("/err/key")
    @api_error_handler
    def err_key():  # pragma: no cover
        # trigger the special handling for missing url
        raise KeyError("url")

    @app.route("/err/conn")
    @api_error_handler
    def err_conn():  # pragma: no cover
        from requests import ConnectionError

        raise ConnectionError("network down")

    @app.route("/err/perm")
    @api_error_handler
    def err_perm():  # pragma: no cover
        raise PermissionError("no access")

    @app.route("/err/unhandled")
    @api_error_handler
    def err_unhandled():  # pragma: no cover
        raise RuntimeError("boom")

    return app


def test_api_error_handler_value_error():
    app = _create_error_app()
    client = app.test_client()

    resp = client.get("/err/value")
    data = resp.get_json()
    assert resp.status_code == 400
    assert data["success"] is False
    assert data["error"] == "参数错误"


def test_api_error_handler_file_not_found():
    app = _create_error_app()
    client = app.test_client()

    resp = client.get("/err/notfound")
    data = resp.get_json()
    assert resp.status_code == 404
    assert data["error"] == "文件未找到"


def test_api_error_handler_key_error_url_has_friendly_message():
    app = _create_error_app()
    client = app.test_client()

    resp = client.get("/err/key")
    data = resp.get_json()
    assert resp.status_code == 400
    # For missing url, a more friendly message should be returned
    assert "返回不完整" in data["message"]


def test_api_error_handler_connection_error():
    app = _create_error_app()
    client = app.test_client()

    resp = client.get("/err/conn")
    data = resp.get_json()
    assert resp.status_code == 503
    assert data["error"] == "网络连接错误"


def test_api_error_handler_permission_error():
    app = _create_error_app()
    client = app.test_client()

    resp = client.get("/err/perm")
    data = resp.get_json()
    assert resp.status_code == 403
    assert data["error"] == "权限错误"


def test_api_error_handler_unhandled_exception():
    app = _create_error_app()
    client = app.test_client()

    resp = client.get("/err/unhandled")
    data = resp.get_json()
    assert resp.status_code == 500
    assert data["success"] is False
    assert data["error"] == "系统错误"
    assert data["error_type"] == "RuntimeError"


def test_safe_json_response_basic():
    app = Flask(__name__)

    with app.app_context():
        resp, status = safe_json_response(success=True, data={"a": 1}, message="ok")
        assert status == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"] == {"a": 1}
        assert data["message"] == "ok"


def test_safe_json_response_includes_request_id_meta():
    app = Flask(__name__)

    with app.test_request_context("/"):
        g.request_id = "req-123"
        resp, status = safe_json_response(success=True)
        assert status == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["meta"]["request_id"] == "req-123"

