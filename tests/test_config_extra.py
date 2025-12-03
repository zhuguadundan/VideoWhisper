import os

import app.config.settings as settings
from app.config.settings import Config


def test_project_root_and_resolve_path(tmp_path, monkeypatch):
    # Point project root to a temporary location
    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)

    # project_root should reflect patched value
    assert Config.project_root() == str(tmp_path)

    # relative paths are resolved against project root
    rel = os.path.join("config", "config.yaml")
    resolved = Config.resolve_path(rel)
    assert resolved == os.path.abspath(os.path.join(str(tmp_path), rel))

    # absolute paths are returned as-is
    abs_path = os.path.join(str(tmp_path), "abs", "file.txt")
    assert Config.resolve_path(abs_path) == abs_path

    # empty path is returned unchanged
    assert Config.resolve_path("") == ""


def test_get_config_returns_empty_dict_when_load_config_fails(monkeypatch):
    # force load_config to raise so get_config must fall back to {}
    def _fail():  # pragma: no cover - behaviour under test is in get_config
        raise FileNotFoundError("missing")

    monkeypatch.setattr(Config, "load_config", staticmethod(_fail))
    Config._config_cache = None

    cfg = Config.get_config()
    assert isinstance(cfg, dict)
    assert cfg == {}


def test_get_https_config_falls_back_to_config_file(tmp_path, monkeypatch):
    # ensure env HTTPS_ENABLED does not short-circuit to env-only config
    monkeypatch.delenv("HTTPS_ENABLED", raising=False)

    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)
    Config._config_cache = None

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cfg_path = config_dir / "config.yaml"
    cfg_path.write_text(
        "https:\n"
        "  enabled: true\n"
        "  port: 1234\n"
        "  host: '127.0.0.1'\n"
        "  auto_generate: false\n"
        "  domain: 'example.com'\n"
        "  country: 'US'\n"
        "  state: 'CA'\n"
        "  organization: 'Example Org'\n"
        "  cert_file: 'config/custom_cert.pem'\n"
        "  key_file: 'config/custom_key.pem'\n",
        encoding="utf-8",
    )

    https_cfg = Config.get_https_config()
    assert https_cfg["enabled"] is True
    assert https_cfg["port"] == 1234
    assert https_cfg["host"] == "127.0.0.1"
    assert https_cfg["domain"] == "example.com"
    assert https_cfg["country"] == "US"
    assert https_cfg["state"] == "CA"
    assert https_cfg["organization"] == "Example Org"

    # paths should be absolute and end with our filenames
    assert os.path.isabs(https_cfg["cert_file"])
    assert os.path.isabs(https_cfg["key_file"])
    assert https_cfg["cert_file"].endswith(os.path.join("config", "custom_cert.pem"))
    assert https_cfg["key_file"].endswith(os.path.join("config", "custom_key.pem"))
