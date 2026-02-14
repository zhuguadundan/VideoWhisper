import types

import pytest

from app.utils.webhook_notifier import send_task_completed_webhooks


class _DummyTask:
    def __init__(self, *, status="completed") -> None:
        self.id = "task-123"
        self.status = status
        self.video_url = "https://example.com/video"
        self.original_filename = "example.mp4"
        self.error_message = ""
        # Minimal video_info stub
        vi = types.SimpleNamespace()
        vi.title = "Example Title"
        vi.url = self.video_url
        vi.duration = 10.0
        vi.uploader = "tester"
        vi.description = "desc"
        self.video_info = vi


def test_noop_when_not_completed(monkeypatch):
    """Tasks that are not completed must not trigger any HTTP calls."""

    called = {"get": 0, "post": 0}

    def fake_get(*args, **kwargs):  # pragma: no cover - defensive
        called["get"] += 1

    def fake_post(*args, **kwargs):  # pragma: no cover - defensive
        called["post"] += 1

    monkeypatch.setattr("app.utils.webhook_notifier.requests.get", fake_get)
    monkeypatch.setattr("app.utils.webhook_notifier.requests.post", fake_post)

    task = _DummyTask(status="processing")
    cfg = {
        "enabled": True,
        "bark": {"enabled": True, "key": "k"},
        "wecom": {"enabled": True, "webhook_url": "https://wx.example"},
    }

    # Should not raise and should not call any HTTP requests
    send_task_completed_webhooks(task, base_config=cfg, runtime_config=None)

    assert called["get"] == 0
    assert called["post"] == 0


def test_bark_and_wecom_called_when_enabled(monkeypatch):
    """When enabled and properly configured, both providers are invoked."""

    calls = {"get": [], "post": []}

    class DummyResp:
        def __init__(self, status_code: int = 200, text: str = "ok") -> None:
            self.status_code = status_code
            self.text = text

    def fake_get(url, params=None, timeout=None):
        calls["get"].append({"url": url, "params": params, "timeout": timeout})
        return DummyResp(200, "bark-ok")

    def fake_post(url, json=None, timeout=None):
        calls["post"].append({"url": url, "json": json, "timeout": timeout})
        return DummyResp(200, "wecom-ok")

    monkeypatch.setattr("app.utils.webhook_notifier.requests.get", fake_get)
    monkeypatch.setattr("app.utils.webhook_notifier.requests.post", fake_post)

    task = _DummyTask(status="completed")
    base_cfg = {
        "enabled": True,
        "base_url": "https://host.example",
        "bark": {
            "enabled": True,
            "server": "https://api.day.app",
            "key": "device-key",
            "group": "VideoWhisper",
        },
        "wecom": {
            "enabled": True,
            "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
            "mentioned_mobile_list": ["13800000000"],
            "mentioned_userid_list": ["user1"],
        },
    }

    send_task_completed_webhooks(task, base_config=base_cfg, runtime_config=None)

    # Bark should be called once with our key and server
    assert len(calls["get"]) == 1
    bark_call = calls["get"][0]
    assert "device-key" in bark_call["url"]
    assert bark_call["params"].get("group") == "VideoWhisper"
    # result URL should be present when base_url is configured
    assert "task-123" in (bark_call["params"].get("url") or "")

    # WeCom should be called once with a text payload
    assert len(calls["post"]) == 1
    wecom_call = calls["post"][0]
    assert wecom_call["url"].startswith("https://qyapi.weixin.qq.com/")
    payload = wecom_call["json"] or {}
    assert payload.get("msgtype") == "text"
    text = (payload.get("text") or {}).get("content", "")
    assert "任务完成" in text
    assert "Example Title" in text
    assert "任务ID: task-123" in text
    assert payload["text"].get("mentioned_mobile_list") == ["13800000000"]
    assert payload["text"].get("mentioned_userid_list") == ["user1"]


def test_runtime_config_overrides_base(monkeypatch):
    """runtime_config should override base_config for nested fields."""

    calls = {"get": []}

    class DummyResp:
        def __init__(self) -> None:
            self.status_code = 200
            self.text = "ok"

    def fake_get(url, params=None, timeout=None):
        calls["get"].append({"url": url, "params": params, "timeout": timeout})
        return DummyResp()

    monkeypatch.setattr("app.utils.webhook_notifier.requests.get", fake_get)
    monkeypatch.setattr(
        "app.utils.webhook_notifier.requests.post", lambda *args, **kwargs: DummyResp()
    )

    task = _DummyTask(status="completed")

    base_cfg = {
        "enabled": True,
        "bark": {"enabled": False, "key": "base-key"},
    }
    runtime_cfg = {
        "bark": {"enabled": True, "key": "runtime-key"},
    }

    send_task_completed_webhooks(task, base_config=base_cfg, runtime_config=runtime_cfg)

    # Bark should be called despite base_config disabling it, because runtime overrides
    assert len(calls["get"]) == 1
    url = calls["get"][0]["url"]
    assert "runtime-key" in url
    assert "base-key" not in url


def test_strict_mode_skips_unsafe_targets_without_http(monkeypatch):
    """When strict mode is enabled, unsafe webhook targets should be skipped.

    This must not raise and must not perform any outbound HTTP calls.
    """

    monkeypatch.setenv("ENFORCE_WEBHOOK_URL_SAFETY", "true")

    # Make policy strict for this test regardless of config.
    monkeypatch.setattr(
        "app.utils.api_guard.get_security_policy",
        lambda: ([], False, False, False),
    )

    called = {"get": 0, "post": 0}

    def fake_get(*args, **kwargs):
        called["get"] += 1
        raise AssertionError("requests.get must not be called in strict skip case")

    def fake_post(*args, **kwargs):
        called["post"] += 1
        raise AssertionError("requests.post must not be called in strict skip case")

    monkeypatch.setattr("app.utils.webhook_notifier.requests.get", fake_get)
    monkeypatch.setattr("app.utils.webhook_notifier.requests.post", fake_post)

    task = _DummyTask(status="completed")
    cfg = {
        "enabled": True,
        "bark": {"enabled": True, "server": "http://127.0.0.1:1234", "key": "k"},
        "wecom": {"enabled": True, "webhook_url": "http://127.0.0.1:5678"},
    }

    send_task_completed_webhooks(task, base_config=cfg, runtime_config=None)
    assert called["get"] == 0
    assert called["post"] == 0
