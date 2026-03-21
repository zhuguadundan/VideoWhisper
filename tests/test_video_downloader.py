import os
import sys
import types

import app.config.settings as settings
from app.config.settings import Config
from app.services.video_downloader import VideoDownloader


def _patch_config_for_tmp(tmp_path, monkeypatch, *, quiet=True):
    monkeypatch.setattr(settings, "_PROJECT_ROOT", str(tmp_path), raising=False)

    def fake_load_config():
        return {
            "system": {
                "temp_dir": "temp",
                "output_dir": "output",
            },
            "downloader": {"general": {"quiet": quiet}},
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


def test_build_base_opts_routes_ytdlp_output_into_logger(tmp_path, monkeypatch):
    _patch_config_for_tmp(tmp_path, monkeypatch, quiet=False)

    vd = VideoDownloader()
    opts = vd._build_base_opts()

    assert opts["quiet"] is True
    assert "logger" in opts
    assert hasattr(opts["logger"], "debug")
    assert hasattr(opts["logger"], "warning")
    assert hasattr(opts["logger"], "error")


def test_get_video_info_cleans_cookie_file_even_on_error(tmp_path, monkeypatch):
    _patch_config_for_tmp(tmp_path, monkeypatch, quiet=False)

    captured_opts = {}

    class DummyYDL:
        def __init__(self, opts):
            captured_opts["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            raise RuntimeError("boom")

    dummy_module = types.SimpleNamespace(YoutubeDL=DummyYDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", dummy_module)

    vd = VideoDownloader()

    try:
        vd.get_video_info("https://example.com/watch?v=1", cookies_str="SID=abc")
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")

    tmp_cookie = captured_opts["opts"].get("_temp_cookiefile")
    assert tmp_cookie
    assert not os.path.exists(tmp_cookie)


def test_download_video_uses_partial_dir_under_output(tmp_path, monkeypatch):
    _patch_config_for_tmp(tmp_path, monkeypatch)

    captured = {}

    class DummyYDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            assert download is True
            outtmpl = captured["opts"]["outtmpl"]
            filename = (
                outtmpl.replace("%(title)s", "Video Title").replace("%(ext)s", "mp4")
            )
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "wb") as f:
                f.write(b"video")
            return {"_filename": filename, "title": "Video Title"}

        def prepare_filename(self, info):  # pragma: no cover - not used in this test
            return info.get("_filename", "video.ext")

    dummy_module = types.SimpleNamespace(YoutubeDL=DummyYDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", dummy_module)

    from app.services import video_downloader as vd_mod

    monkeypatch.setattr(
        vd_mod, "_build_timestamp_suffix", lambda dt=None: "20260315_160000"
    )

    vd = VideoDownloader()
    out_dir = tmp_path / "output" / "task-1"

    result_path = vd.download_video(
        url="https://example.com/watch?v=1",
        output_dir=str(out_dir),
        task_id="task-1",
    )

    partial_dir = out_dir / ".partial"
    assert captured["opts"]["outtmpl"] == str(partial_dir / "%(title)s_task-1.%(ext)s")
    assert result_path == str(out_dir / "Video Title_20260315_160000.mp4")
    assert os.path.exists(result_path)
    assert not partial_dir.exists()


def test_download_video_uses_cleaned_stem_when_info_title_missing(
    tmp_path, monkeypatch
):
    _patch_config_for_tmp(tmp_path, monkeypatch)

    captured = {}

    class DummyYDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            assert download is True
            outtmpl = captured["opts"]["outtmpl"]
            filename = (
                outtmpl.replace("%(title)s", "Downloaded Clip")
                .replace("%(ext)s", "mp4")
            )
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "wb") as f:
                f.write(b"video")
            return {"_filename": filename}

        def prepare_filename(self, info):  # pragma: no cover - not used in this test
            return info.get("_filename", "video.ext")

    dummy_module = types.SimpleNamespace(YoutubeDL=DummyYDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", dummy_module)

    from app.services import video_downloader as vd_mod

    monkeypatch.setattr(
        vd_mod, "_build_timestamp_suffix", lambda dt=None: "20260315_160000"
    )

    vd = VideoDownloader()
    out_dir = tmp_path / "output" / "task-2"

    result_path = vd.download_video(
        url="https://example.com/watch?v=2",
        output_dir=str(out_dir),
        task_id="task-2",
    )

    assert os.path.basename(result_path) == "Downloaded Clip_20260315_160000.mp4"
    assert "task-2" not in os.path.basename(result_path)


def test_download_video_cleans_partial_dir_on_failure(tmp_path, monkeypatch):
    _patch_config_for_tmp(tmp_path, monkeypatch)

    captured = {}

    class DummyYDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            assert download is True
            outtmpl = captured["opts"]["outtmpl"]
            filename = (
                outtmpl.replace("%(title)s", "Broken Video").replace("%(ext)s", "mp4")
            )
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "wb") as f:
                f.write(b"partial-data")
            raise RuntimeError("boom")

    dummy_module = types.SimpleNamespace(YoutubeDL=DummyYDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", dummy_module)

    vd = VideoDownloader()
    task_id = "4e0d2e56-6d76-4df0-9eaf-0f4e41c8f112"
    out_dir = tmp_path / "output" / task_id

    try:
        vd.download_video(
            url="https://example.com/watch?v=3",
            output_dir=str(out_dir),
            task_id=task_id,
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")

    assert not (out_dir / ".partial").exists()
