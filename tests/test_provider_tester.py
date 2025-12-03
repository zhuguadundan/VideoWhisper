import os
import sys
import types

from app.utils import provider_tester


def test_test_siliconflow_success_and_error(monkeypatch):
    calls = {}

    def fake_get_ok(url, headers, timeout):  # noqa: D401
        calls["url"] = url
        calls["headers"] = headers

        class Resp:
            def __init__(self):
                self.status_code = 200

        return Resp()

    dummy_requests_ok = types.SimpleNamespace(get=fake_get_ok)
    monkeypatch.setitem(sys.modules, "requests", dummy_requests_ok)

    ok, msg = provider_tester.test_siliconflow(
        api_key="key123", base_url="https://api.example.com/v1", model="m1"
    )
    assert ok is True
    assert calls["url"].endswith("/models")
    assert calls["headers"]["Authorization"] == "Bearer key123"

    # Non-200 status should be reported as failure
    def fake_get_bad(url, headers, timeout):  # noqa: D401
        class Resp:
            def __init__(self):
                self.status_code = 500

        return Resp()

    dummy_requests_bad = types.SimpleNamespace(get=fake_get_bad)
    monkeypatch.setitem(sys.modules, "requests", dummy_requests_bad)

    ok2, msg2 = provider_tester.test_siliconflow(api_key="key123", base_url="https://api.example.com/v1")
    assert ok2 is False
    assert "500" in msg2


def test_test_openai_compatible_success_and_empty(monkeypatch):
    # Success path: models.list() returns non-empty iterable
    class DummyClient:
        def __init__(self, api_key, base_url=None):  # noqa: D401
            self.api_key = api_key
            self.base_url = base_url
            self.models = types.SimpleNamespace(list=lambda: ["m1"])  # non-empty

    dummy_openai_ok = types.SimpleNamespace(OpenAI=DummyClient)
    monkeypatch.setitem(sys.modules, "openai", dummy_openai_ok)

    ok, msg = provider_tester.test_openai_compatible(
        api_key="k", base_url="https://api.openai.example", model="gpt-4"
    )
    assert ok is True
    assert "gpt-4" in msg

    # Empty model list should be treated as failure
    class DummyClientEmpty:
        def __init__(self, api_key, base_url=None):  # noqa: D401
            self.models = types.SimpleNamespace(list=lambda: [])

    dummy_openai_empty = types.SimpleNamespace(OpenAI=DummyClientEmpty)
    monkeypatch.setitem(sys.modules, "openai", dummy_openai_empty)

    ok2, msg2 = provider_tester.test_openai_compatible(api_key="k")
    assert ok2 is False
    assert "模型列表为空" in msg2 or "模型" in msg2


def test_test_gemini_success(monkeypatch):
    captured = {}

    def fake_configure(api_key):  # noqa: D401
        captured["api_key"] = api_key

    class DummyModel:
        def __init__(self, model):  # noqa: D401
            captured["model"] = model

        def generate_content(self, text):  # noqa: D401
            captured["text"] = text
            return object()

    dummy_genai = types.SimpleNamespace(
        configure=fake_configure,
        GenerativeModel=DummyModel,
    )

    # Replace the generativeai submodule and also bind it on the google package if present
    monkeypatch.setitem(sys.modules, "google.generativeai", dummy_genai)
    google_pkg = sys.modules.get("google")
    if google_pkg is not None:
        monkeypatch.setattr(google_pkg, "generativeai", dummy_genai, raising=False)

    ok, msg = provider_tester.test_gemini(
        api_key="gem-key", base_url="https://gem.example", model="gem-model"
    )

    assert ok is True
    assert "gem-model" in msg
    assert captured["api_key"] == "gem-key"
    assert captured["model"] == "gem-model"
    assert captured["text"] == "Hello"
    # base_url should be exported via env when provided
    assert os.environ["GOOGLE_AI_STUDIO_API_URL"] == "https://gem.example"
