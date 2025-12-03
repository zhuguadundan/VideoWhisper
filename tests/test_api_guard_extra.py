import os

import app.config.settings as settings
from app.config.settings import Config
from app.utils import api_guard


def test_get_security_policy_merges_config_and_env_hosts(tmp_path, monkeypatch):
    # Prepare config with some allowed hosts and security flags
    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)
    Config._config_cache = None

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cfg_path = config_dir / "config.yaml"
    cfg_path.write_text(
        "security:\n"
        "  allowed_api_hosts:\n"
        "    - api.example.com\n"
        "    - Example.com\n"
        "  allow_insecure_http: false\n"
        "  allow_private_addresses: false\n"
        "  enforce_api_hosts_whitelist: true\n",
        encoding="utf-8",
    )

    # env adds extra host and duplicates existing one
    monkeypatch.setenv("ALLOWED_API_HOSTS", "another.com,api.example.com")
    monkeypatch.delenv("ALLOW_INSECURE_HTTP", raising=False)
    monkeypatch.delenv("ALLOW_PRIVATE_ADDRESSES", raising=False)
    monkeypatch.delenv("ENFORCE_API_HOSTS_WHITELIST", raising=False)

    allowed_hosts, allow_http, allow_private, enforce_whitelist = api_guard.get_security_policy()

    # host list is de-duplicated and lower-cased
    assert set(allowed_hosts) == {"api.example.com", "example.com", "another.com"}
    # booleans come from config when env unset
    assert allow_http is False
    assert allow_private is False
    assert enforce_whitelist is True


def test_get_security_policy_env_overrides_booleans(tmp_path, monkeypatch):
    # Base config disables http/private and enables whitelist
    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)
    Config._config_cache = None

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cfg_path = config_dir / "config.yaml"
    cfg_path.write_text(
        "security:\n"
        "  allowed_api_hosts: []\n"
        "  allow_insecure_http: false\n"
        "  allow_private_addresses: false\n"
        "  enforce_api_hosts_whitelist: true\n",
        encoding="utf-8",
    )

    # env flips all three flags
    monkeypatch.setenv("ALLOW_INSECURE_HTTP", "true")
    monkeypatch.setenv("ALLOW_PRIVATE_ADDRESSES", "true")
    monkeypatch.setenv("ENFORCE_API_HOSTS_WHITELIST", "false")

    allowed_hosts, allow_http, allow_private, enforce_whitelist = api_guard.get_security_policy()

    assert allowed_hosts == []
    assert allow_http is True
    assert allow_private is True
    assert enforce_whitelist is False
