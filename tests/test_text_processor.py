import types

import pytest

from app.services.text_processor import TextProcessor


def _build_tp_with_configs():
    openai_cfg = {"api_key": "key-openai", "base_url": "https://api.openai.example", "model": "gpt-4"}
    gemini_cfg = {"api_key": "key-gemini", "base_url": "https://gemini.example", "model": "gemini-pro"}
    sf_cfg = {"api_key": "key-sf", "base_url": "https://api.siliconflow.cn/v1", "model": "m"}
    return TextProcessor(openai_config=openai_cfg, gemini_config=gemini_cfg, siliconflow_config=sf_cfg)


def test_ensure_openai_client_requires_api_key(monkeypatch):
    tp = _build_tp_with_configs()
    # Remove api_key to force error path
    tp.openai_config["api_key"] = ""

    with pytest.raises(ValueError):
        tp._ensure_openai_client()


def test_ensure_openai_client_success(monkeypatch):
    tp = _build_tp_with_configs()

    class DummyClient:
        def __init__(self, api_key, base_url=None):  # noqa: D401
            self.api_key = api_key
            self.base_url = base_url

    dummy_module = types.SimpleNamespace(OpenAI=DummyClient)
    monkeypatch.setattr("app.services.text_processor.openai", dummy_module)

    client = tp._ensure_openai_client()
    assert isinstance(client, DummyClient)
    assert client.api_key == "key-openai"
    assert client.base_url == "https://api.openai.example"


def test_get_available_and_default_providers():
    tp = _build_tp_with_configs()

    # Pretend all three clients are available and runtime custom provider is enabled
    tp.siliconflow_client = object()
    tp.openai_client = object()
    tp.runtime_custom_provider = True
    tp.gemini_model = object()

    providers = tp.get_available_providers()
    # Order is not strictly essential here, but membership is
    assert set(providers) == {"siliconflow", "custom", "gemini"}

    default = tp.get_default_provider()
    # Priority: siliconflow > custom > openai > gemini
    assert default == "siliconflow"


def test_estimate_tokens_and_split_text():
    tp = _build_tp_with_configs()
    text = "abcdef"
    est = tp.estimate_tokens(text)
    assert est == int(len(text) * tp.TOKEN_ESTIMATE_RATIO)

    # Short text under limit -> single segment
    segments = tp.split_text_intelligently("short", max_chars=10)
    assert segments == ["short"]

    # Long text with paragraph and sentence level splitting
    long_text = "para1 sentence1. sentence2.\n\npara2 sentence3."
    segments2 = tp.split_text_intelligently(long_text, max_chars=20)
    # Should produce multiple segments but cover both branches
    assert isinstance(segments2, list)
    assert len(segments2) >= 2

