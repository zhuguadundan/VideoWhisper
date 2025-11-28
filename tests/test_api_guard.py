import pytest

from app.utils import api_guard


def test_is_safe_base_url_allows_https_public_by_default():
    assert api_guard.is_safe_base_url("https://example.com") is True


def test_is_safe_base_url_blocks_private_when_disallowed():
    # Private and local addresses should be blocked when allow_private=False
    assert not api_guard.is_safe_base_url("http://127.0.0.1", allow_private=False)
    assert not api_guard.is_safe_base_url("http://192.168.1.10", allow_private=False)
    assert not api_guard.is_safe_base_url("http://10.0.0.1", allow_private=False)


def test_is_safe_base_url_enforces_whitelist():
    allowed = ["allowed.com"]
    # Exact host or subdomain should be allowed
    assert api_guard.is_safe_base_url(
        "https://allowed.com/path",
        allowed_hosts=allowed,
        enforce_whitelist=True,
    )
    assert api_guard.is_safe_base_url(
        "https://api.allowed.com",
        allowed_hosts=allowed,
        enforce_whitelist=True,
    )
    # Other hosts should be rejected
    assert not api_guard.is_safe_base_url(
        "https://evil.com",
        allowed_hosts=allowed,
        enforce_whitelist=True,
    )


def test_validate_runtime_api_config_rejects_unsafe_base_url(monkeypatch):
    """Unsafe base URLs should trigger ValueError."""

    def fake_policy():
        # allowed_hosts, allow_http, allow_private, enforce_whitelist
        return [], True, False, False

    monkeypatch.setattr(api_guard, "get_security_policy", fake_policy, raising=False)

    api_config = {
        "text_processor": {"base_url": "http://127.0.0.1"},
        "siliconflow": {"base_url": "https://api.siliconflow.cn"},
    }

    with pytest.raises(ValueError) as exc:
        api_guard.validate_runtime_api_config(api_config)
    assert "不安全的Base URL" in str(exc.value)


def test_validate_runtime_api_config_accepts_safe_urls(monkeypatch):
    def fake_policy():
        return [], True, False, False

    monkeypatch.setattr(api_guard, "get_security_policy", fake_policy, raising=False)

    api_config = {
        "text_processor": {"base_url": "https://example.com"},
        "siliconflow": {"base_url": "https://api.siliconflow.cn"},
    }

    # Should not raise
    api_guard.validate_runtime_api_config(api_config)

