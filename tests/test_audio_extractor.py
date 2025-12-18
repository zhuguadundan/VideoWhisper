import os
import types
import wave

import app.config.settings as settings
from app.config.settings import Config
from app.services.audio_extractor import AudioExtractor


def _patch_config_for_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)

    def fake_load_config():
        return {
            "system": {
                "temp_dir": "temp",
                "output_dir": "output",
                "audio_format": "wav",
                "audio_sample_rate": 16000,
            }
        }

    monkeypatch.setattr(Config, "load_config", staticmethod(fake_load_config))
    Config._config_cache = None


def test_audio_extractor_sanitize_filename():
    extractor = AudioExtractor.__new__(AudioExtractor)  # bypass __init__

    name = extractor._sanitize_filename("  <inv*alid>.mp4  ")
    assert "<" not in name and ">" not in name and "*" not in name
    assert "inv" in name


def test_extract_audio_from_video_and_cleanup(tmp_path, monkeypatch):
    _patch_config_for_tmp(tmp_path, monkeypatch)

    from app.services import audio_extractor as ae_mod

    # Prepare a fake video file
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")

    calls = {}

    class DummyStream:
        def __init__(self, path):  # noqa: D401
            self.path = path

        def output(self, out_path, acodec=None, ar=None, ac=None):  # noqa: D401
            calls["output"] = {
                "out_path": out_path,
                "acodec": acodec,
                "ar": ar,
                "ac": ac,
            }
            return self

        def run(self, overwrite_output=False, quiet=None, cmd=None):  # noqa: D401
            # simulate ffmpeg writing the output file
            os.makedirs(os.path.dirname(calls["output"]["out_path"]), exist_ok=True)
            with open(calls["output"]["out_path"], "wb") as f:
                f.write(b"audio")

    dummy_ffmpeg = types.SimpleNamespace(
        input=lambda path, **kwargs: DummyStream(path)
    )

    monkeypatch.setattr(ae_mod, "ffmpeg", dummy_ffmpeg)

    extractor = AudioExtractor()
    out = extractor.extract_audio_from_video(str(video_path))

    assert out.endswith(".wav")
    assert os.path.exists(out)
    assert calls["output"]["acodec"] == "pcm_s16le"
    assert calls["output"]["ar"] == extractor.sample_rate
    assert calls["output"]["ac"] == 1


def test_convert_audio_format_uses_target_settings(tmp_path, monkeypatch):
    _patch_config_for_tmp(tmp_path, monkeypatch)

    from app.services import audio_extractor as ae_mod

    # prepare a fake input audio file
    src = tmp_path / "src.wav"
    src.write_bytes(b"data")

    calls = {}

    class DummyStream:
        def __init__(self, path):  # noqa: D401
            self.path = path

    def fake_input(path):  # noqa: D401
        return DummyStream(path)

    def fake_output(stream, out_path, **kwargs):  # noqa: D401
        calls["output"] = {"out_path": out_path, **kwargs}
        return stream

    def fake_run(stream, quiet=None, overwrite_output=None, cmd=None):  # noqa: D401
        os.makedirs(os.path.dirname(calls["output"]["out_path"]), exist_ok=True)
        with open(calls["output"]["out_path"], "wb") as f:
            f.write(b"converted")

    dummy_ffmpeg = types.SimpleNamespace(
        input=fake_input,
        output=fake_output,
        run=fake_run,
    )

    monkeypatch.setattr(ae_mod, "ffmpeg", dummy_ffmpeg)

    extractor = AudioExtractor()
    out_path = str(tmp_path / "out.wav")

    result = extractor.convert_audio_format(str(src), out_path, target_format="wav", sample_rate=8000)
    assert result == out_path
    assert os.path.exists(out_path)
    assert calls["output"]["acodec"] == "pcm_s16le"
    assert calls["output"]["ar"] == 8000
    assert calls["output"]["ac"] == 1


def test_probe_duration_seconds_uses_format_and_streams():
    extractor = AudioExtractor.__new__(AudioExtractor)

    # format.duration path
    d1 = extractor._probe_duration_seconds({"format": {"duration": "12.5"}})
    assert d1 == 12.5

    # fallback to audio stream duration
    probe = {
        "format": {},
        "streams": [
            {"codec_type": "video", "duration": "5"},
            {"codec_type": "audio", "duration": "7.5"},
        ],
    }
    d2 = extractor._probe_duration_seconds(probe)
    assert d2 == 7.5

    # missing data -> 0.0
    d3 = extractor._probe_duration_seconds({})
    assert d3 == 0.0


def test_split_audio_by_duration_and_get_audio_info(tmp_path, monkeypatch):
    _patch_config_for_tmp(tmp_path, monkeypatch)

    from app.services import audio_extractor as ae_mod

    audio_path = tmp_path / "audio.wav"
    # Create a minimal valid WAV (mono, 16-bit, 16kHz, 10s)
    with wave.open(str(audio_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000 * 10)

    class DummySegStream:
        def __init__(self, path, ss=None, t=None):  # noqa: D401
            self.path = path
            self.ss = ss
            self.t = t

        def output(self, out_path, acodec=None, ar=None, ac=None):  # noqa: D401
            # simulate writing out the segment
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(b"segment")
            return self

        def run(self, quiet=None, overwrite_output=None, cmd=None):  # noqa: D401
            return None

    def fake_input(path, ss=None, t=None):  # noqa: D401
        return DummySegStream(path, ss=ss, t=t)

    dummy_ffmpeg = types.SimpleNamespace(input=fake_input)

    monkeypatch.setattr(ae_mod, "ffmpeg", dummy_ffmpeg)

    extractor = AudioExtractor()
    segments = extractor.split_audio_by_duration(str(audio_path), segment_duration=4)

    # duration=10, segment_duration=4 -> 3 segments
    assert len(segments) == 3
    assert segments[0]["start_time"] == 0
    assert segments[0]["end_time"] == 4

    info = extractor.get_audio_info(str(audio_path))
    assert info["duration"] == 10.0
    assert info["sample_rate"] == 16000
    assert info["channels"] == 1
    assert info["codec"] == "pcm_s16le"
    assert info["size"] == os.path.getsize(audio_path)
