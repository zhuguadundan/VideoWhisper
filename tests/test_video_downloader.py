import os
import sys
import types

import app.config.settings as settings
from app.config.settings import Config
from app.services.video_downloader import VideoDownloader


def _patch_config_for_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)

    def fake_load_config():
        return {
            "system": {
                "temp_dir": "temp",
                "output_dir": "output",
            },
            "downloader": {"general": {"quiet": True}},
        }

    monkeypatch.setattr(Config, "load_config", staticmethod(fake_load_config))
    Config._config_cache = None


def test_get_ffmpeg_path_uses_shutil_which(monkeypatch, tmp_path):
    _patch_config_for_tmp(tmp_path, monkeypatch)

    from app.services import video_downloader as vd_mod

    vd = VideoDownloader()

    def fake_which(_name):  # noqa: D401
        return "/usr/bin/ffmpeg"

    monkeypatch.setattr(vd_mod.shutil, "which", fake_which)

    path = vd._get_ffmpeg_path()
    assert path == "/usr/bin/ffmpeg"


def test_get_video_info_flattens_playlist_and_cleans_cookie(tmp_path, monkeypatch):
    _patch_config_for_tmp(tmp_path, monkeypatch)

    captured_opts = {}

    class DummyYDL:
        def __init__(self, opts):  # noqa: D401
            captured_opts["opts"] = opts

        def __enter__(self):  # noqa: D401
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: D401
            return False

        def extract_info(self, url, download=False):  # noqa: D401
            assert download is False
            # simulate playlist structure
            return {
                "entries": [
                    {
                        "id": "vid1",
                        "title": "Video Title",
                        "uploader": "Uploader",
                        "duration": 12,
                        "webpage_url": "https://example.com/watch?v=1",
                        "ext": "mp4",
                    }
                ]
            }

    dummy_module = types.SimpleNamespace(YoutubeDL=DummyYDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", dummy_module)

    vd = VideoDownloader()
    info = vd.get_video_info("https://example.com/watch?v=1", cookies_str="SID=abc")

    assert info["id"] == "vid1"
    assert info["title"] == "Video Title"
    assert info["uploader"] == "Uploader"
    assert info["duration"] == 12
    assert info["url"] == "https://example.com/watch?v=1"

    opts = captured_opts["opts"]
    tmp_cookie = opts.get("_temp_cookiefile")
    # temp cookie file should have been removed by cleanup logic
    if tmp_cookie:
        assert not os.path.exists(tmp_cookie)


def test_download_audio_only_uses_outdir_and_returns_existing_file(tmp_path, monkeypatch):
    _patch_config_for_tmp(tmp_path, monkeypatch)

    captured = {}

    class DummyYDL:
        def __init__(self, opts):  # noqa: D401
            captured["opts"] = opts

        def __enter__(self):  # noqa: D401
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: D401
            return False

        def extract_info(self, url, download=False):  # noqa: D401
            assert download is True
            # Simulate yt_dlp returning a filename
            outtmpl = captured["opts"]["outtmpl"]
            # Pretend final processed file is mp3 with the same template
            filename = outtmpl.replace("%(title)s", "Video")
            mp3_path = os.path.splitext(filename)[0] + ".mp3"
            os.makedirs(os.path.dirname(mp3_path), exist_ok=True)
            with open(mp3_path, "wb") as f:
                f.write(b"data")
            return {"_filename": mp3_path}

        def prepare_filename(self, info):  # pragma: no cover - not used in this test
            return info.get("_filename", "video.ext")

    dummy_module = types.SimpleNamespace(YoutubeDL=DummyYDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", dummy_module)

    vd = VideoDownloader()
    out_dir = tmp_path / "out"

    result_path = vd.download_audio_only(
        url="https://example.com/watch?v=1", task_id="task-1", output_path=str(out_dir)
    )

    assert result_path.endswith(".mp3")
    assert os.path.commonpath([str(out_dir)]) == os.path.commonpath(
        [str(out_dir), os.path.abspath(result_path)]
    )
    assert os.path.exists(result_path)
