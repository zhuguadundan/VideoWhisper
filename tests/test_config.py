import os

import app.config.settings as settings
from app.config.settings import Config, _resolve_secret_key


def test_load_config_uses_project_root(tmp_path, monkeypatch):
    """Config.load_config should read from _PROJECT_ROOT/config/config.yaml."""

    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)
    Config._config_cache = None

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cfg_path = config_dir / "config.yaml"
    cfg_path.write_text(
        "apis:\n"
        "  siliconflow:\n"
        "    api_key: 'test-key'\n"
        "web:\n"
        "  port: 12345\n",
        encoding="utf-8",
    )

    cfg = Config.load_config()
    assert cfg["apis"]["siliconflow"]["api_key"] == "test-key"
    assert cfg["web"]["port"] == 12345


def test_get_api_config_reads_from_loaded_config(tmp_path, monkeypatch):
    """Config.get_api_config should return the service section from config."""

    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)
    Config._config_cache = None

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text(
        "apis:\n"
        "  siliconflow:\n"
        "    api_key: 'sf-key'\n"
        "  openai:\n"
        "    api_key: 'oa-key'\n",
        encoding="utf-8",
    )

    cfg_sf = Config.get_api_config("siliconflow")
    cfg_oa = Config.get_api_config("openai")
    assert cfg_sf["api_key"] == "sf-key"
    assert cfg_oa["api_key"] == "oa-key"


def test_get_https_config_env_override(monkeypatch):
    """When HTTPS_ENABLED is set, HTTPS config should be driven by env vars."""

    Config._config_cache = None

    monkeypatch.setenv("HTTPS_ENABLED", "true")
    monkeypatch.setenv("HTTPS_PORT", "8443")
    monkeypatch.setenv("HTTPS_HOST", "127.0.0.1")
    monkeypatch.setenv("CERT_AUTO_GENERATE", "false")
    monkeypatch.setenv("CERT_DOMAIN", "example.com")
    monkeypatch.setenv("CERT_COUNTRY", "US")
    monkeypatch.setenv("CERT_STATE", "CA")
    monkeypatch.setenv("CERT_ORGANIZATION", "Example Org")
    monkeypatch.setenv("CERT_FILE", "config/custom_cert.pem")
    monkeypatch.setenv("KEY_FILE", "config/custom_key.pem")

    https_cfg = Config.get_https_config()
    assert https_cfg["enabled"] is True
    assert https_cfg["port"] == 8443
    assert https_cfg["host"] == "127.0.0.1"
    assert https_cfg["domain"] == "example.com"
    assert https_cfg["country"] == "US"
    assert https_cfg["state"] == "CA"
    assert https_cfg["organization"] == "Example Org"
    # cert/key paths should be absolute and include our filenames
    assert os.path.isabs(https_cfg["cert_file"])
    assert os.path.isabs(https_cfg["key_file"])
    assert https_cfg["cert_file"].endswith(os.path.join("config", "custom_cert.pem"))
    assert https_cfg["key_file"].endswith(os.path.join("config", "custom_key.pem"))


def test_resolve_secret_key_prefers_env(tmp_path, monkeypatch):
    """_resolve_secret_key must prefer SECRET_KEY env over files."""

    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)
    Config._config_cache = None

    monkeypatch.setenv("SECRET_KEY", "env-secret-key")
    key = _resolve_secret_key()
    assert key == "env-secret-key"


def test_resolve_secret_key_persists_to_file(tmp_path, monkeypatch):
    """Without SECRET_KEY env, it should generate and persist to config/.secret_key."""

    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)
    Config._config_cache = None

    monkeypatch.delenv("SECRET_KEY", raising=False)

    key1 = _resolve_secret_key()
    secret_file = tmp_path / "config" / ".secret_key"
    assert secret_file.exists()
    saved = secret_file.read_text(encoding="utf-8").strip()
    assert saved == key1

    monkeypatch.delenv("SECRET_KEY", raising=False)
    key2 = _resolve_secret_key()
    assert key2 == key1

