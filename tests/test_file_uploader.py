import io
import os

import pytest

from app.services.file_uploader import FileUploader
from app.config.settings import Config


def _make_minimal_config(temp_dir: str):
    return {
        "system": {
            "temp_dir": temp_dir,
        },
        "upload": {
            "max_upload_size": 1,  # MB
            "upload_chunk_size": 1,
            "allowed_video_formats": ["mp4"],
            "allowed_audio_formats": ["mp3"],
        },
    }


def test_get_file_info_video_and_audio(tmp_path, monkeypatch):
    cfg = _make_minimal_config(str(tmp_path / "temp"))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    fu = FileUploader()

    info_video = fu._get_file_info("movie.mp4", 123)
    assert info_video["file_type"] == "video"
    assert info_video["need_audio_extraction"] is True
    assert info_video["file_ext"] == "mp4"

    info_audio = fu._get_file_info("sound.mp3", 456)
    assert info_audio["file_type"] == "audio"
    assert info_audio["need_audio_extraction"] is False
    assert info_audio["file_ext"] == "mp3"


def test_get_file_info_unsupported_extension_raises(tmp_path, monkeypatch):
    cfg = _make_minimal_config(str(tmp_path / "temp"))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    fu = FileUploader()

    with pytest.raises(ValueError):
        fu._get_file_info("file.xyz", 10)


def test_validate_file_size_limit(tmp_path, monkeypatch):
    cfg = _make_minimal_config(str(tmp_path / "temp"))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    fu = FileUploader()
    max_bytes = fu.max_upload_size

    # Just under the limit should be allowed
    is_valid, msg = fu._validate_file("movie.mp4", max_bytes - 1, "video/mp4")
    assert is_valid

    # Above the limit should be rejected
    is_valid2, msg2 = fu._validate_file("movie.mp4", max_bytes + 1, "video/mp4")
    assert not is_valid2
    assert isinstance(msg2, str) and msg2


def test_save_uploaded_file_writes_to_temp_dir(tmp_path, monkeypatch):
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    cfg = _make_minimal_config(str(temp_root))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    fu = FileUploader()

    data = b"hello world" * 100
    file_obj = io.BytesIO(data)
    original_filename = "movie.mp4"
    file_size = len(data)

    result = fu.save_uploaded_file(file_obj, original_filename, file_size)

    assert isinstance(result, dict)
    assert result.get("success") is True
    file_path = result.get("file_path")
    assert file_path
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) == file_size

