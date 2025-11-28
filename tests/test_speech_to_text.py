import io
import os

import pytest

from app.services.speech_to_text import SpeechToText


def test_transcribe_audio_requires_api_key(tmp_path, monkeypatch):
    # Provide empty api_key in config
    cfg = {"api_key": "", "base_url": "https://api.siliconflow.cn/v1", "model": "m"}
    st = SpeechToText(api_config=cfg)

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    with pytest.raises(ValueError):
        st.transcribe_audio(str(audio))


def test_transcribe_audio_file_not_found(tmp_path):
    st = SpeechToText(api_config={"api_key": "k", "base_url": "https://api.siliconflow.cn/v1", "model": "m"})

    missing = tmp_path / "missing.wav"
    with pytest.raises(FileNotFoundError):
        st.transcribe_audio(str(missing))


def test_transcribe_audio_success_single_attempt(tmp_path, monkeypatch):
    st = SpeechToText(api_config={"api_key": "k", "base_url": "https://api.siliconflow.cn/v1", "model": "m"})

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake-audio")

    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(url, headers, files, data, timeout):  # noqa: D401, signature matches requests.post
        # Validate that we point to the correct endpoint
        assert url.endswith("/audio/transcriptions")
        return DummyResponse({"text": "hello world"})

    monkeypatch.setattr("app.services.speech_to_text.requests.post", fake_post)

    result = st.transcribe_audio(str(audio))
    assert result["text"] == "hello world"
    assert result["segments"] == []
    assert result["language"] == "unknown"


def test_transcribe_audio_retries_on_empty_text(tmp_path, monkeypatch):
    st = SpeechToText(api_config={"api_key": "k", "base_url": "https://api.siliconflow.cn/v1", "model": "m"})

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake-audio")

    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    calls = {"count": 0}

    def fake_post(url, headers, files, data, timeout):
        calls["count"] += 1
        # 前两次返回空文本, 第三次返回有效文本
        if calls["count"] < 3:
            return DummyResponse({"text": "  "})
        return DummyResponse({"text": "ok text"})

    monkeypatch.setattr("app.services.speech_to_text.requests.post", fake_post)

    result = st.transcribe_audio(str(audio))
    assert result["text"] == "ok text"
    assert calls["count"] == 3


def test_format_transcript_and_get_full_text():
    st = SpeechToText(api_config={"api_key": "k", "base_url": "https://api.siliconflow.cn/v1", "model": "m"})

    results = [
        {"segment_index": 0, "text": "first", "error": None},
        {"segment_index": 1, "error": "x"},
        {"segment_index": 2, "text": "second", "error": None},
    ]

    transcript = st.format_transcript(results)
    assert "first" in transcript
    assert "second" in transcript
    assert "片段 2" in transcript  # error line

    full = st.get_full_text(results)
    assert full == "first second"

