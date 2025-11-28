import os

import pytest

from app import create_app
from app.config.settings import Config


@pytest.fixture(autouse=True)
def _restore_selected_env(monkeypatch):
    """Keep a small set of security-related env vars isolated per test."""

    keys = [
        "ADMIN_TOKEN",
        "ENFORCE_ADMIN_TOKEN",
        "FLASK_ENV",
        "HTTPS_ENABLED",
        "ALLOW_INSECURE_HTTP",
        "ALLOW_PRIVATE_ADDRESSES",
        "ALLOWED_API_HOSTS",
    ]
    original = {k: os.environ.get(k) for k in keys}

    yield

    for k, v in original.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)


@pytest.fixture
def app_config(tmp_path, monkeypatch):
    """Provide a minimal but realistic config dict for create_app()."""

    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = {
        "apis": {
            "siliconflow": {"api_key": "", "base_url": "https://api.siliconflow.cn/v1", "model": "m"},
            "openai": {"api_key": "", "base_url": "", "model": "gpt-4"},
            "gemini": {"api_key": "", "base_url": "", "model": "gemini-pro"},
        },
        "system": {
            "temp_dir": str(temp_dir),
            "output_dir": str(output_dir),
            "max_file_size": 500,
            "audio_format": "wav",
            "audio_sample_rate": 16000,
        },
        "processing": {},
        "security": {
            "allowed_api_hosts": [],
            "allow_insecure_http": False,
            "allow_private_addresses": False,
            "enforce_api_hosts_whitelist": False,
        },
        "web": {"host": "0.0.0.0", "port": 5000, "debug": False},
        "https": {
            "enabled": False,
            "port": 5443,
            "host": "0.0.0.0",
            "auto_generate": False,
            "domain": "localhost",
            "country": "CN",
            "state": "BJ",
            "organization": "Test",
            "cert_file": str(tmp_path / "config" / "cert.pem"),
            "key_file": str(tmp_path / "config" / "key.pem"),
        },
        "downloader": {"general": {"format": "best", "audio_format": "bestaudio", "quiet": True}},
        "upload": {
            "max_upload_size": 10,
            "upload_chunk_size": 1,
            "allowed_video_formats": ["mp4"],
            "allowed_audio_formats": ["mp3"],
        },
    }

    # Ensure Config.load_config uses our in-memory config
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))
    Config._config_cache = None
    return cfg


@pytest.fixture
def api_app(app_config):
    """Flask app configured with a test config, for API tests."""

    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(api_app):
    return api_app.test_client()
