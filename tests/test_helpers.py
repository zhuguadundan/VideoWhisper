import os

from app.utils import helpers


def test_ensure_directory_exists_idempotent(tmp_path):
    target = tmp_path / "subdir"
    # directory does not exist initially
    assert not target.exists()

    helpers.ensure_directory_exists(str(target))
    assert target.is_dir()

    # calling again should not raise and directory remains
    helpers.ensure_directory_exists(str(target))
    assert target.is_dir()


def test_clean_directory_removes_all_except_kept(tmp_path):
    root = tmp_path
    keep = root / "keep.txt"
    remove_file = root / "remove.txt"
    subdir = root / "subdir"

    keep.write_text("k", encoding="utf-8")
    remove_file.write_text("r", encoding="utf-8")
    subdir.mkdir()
    (subdir / "inner.txt").write_text("x", encoding="utf-8")

    helpers.clean_directory(str(root), keep_files=["keep.txt"])

    assert keep.exists()
    assert not remove_file.exists()
    # directory and its contents should be removed
    assert not subdir.exists()


def test_format_file_size_basic_units():
    assert helpers.format_file_size(0) == "0B"
    assert helpers.format_file_size(1) == "1.0 B"
    assert helpers.format_file_size(1024) == "1.0 KB"
    assert helpers.format_file_size(1024 * 1024) == "1.0 MB"


def test_is_valid_url_variants():
    assert helpers.is_valid_url("http://example.com") is True
    assert helpers.is_valid_url("https://localhost:8080/path") is True
    assert helpers.is_valid_url("ftp://example.com") is False
    assert helpers.is_valid_url("not-a-url") is False


def test_sanitize_filename_handles_illegal_chars_and_length():
    # illegal characters replaced with underscore and trimmed
    name = helpers.sanitize_filename("  <inv*alid>.txt  ")
    assert "<" not in name and ">" not in name and "*" not in name
    assert "inv" in name

    # empty -> default name
    assert helpers.sanitize_filename("", default_name="fallback") == "fallback"

    # overly long name is truncated
    long_name = "a" * 300
    truncated = helpers.sanitize_filename(long_name, max_length=50)
    assert len(truncated) == 50


def test_get_video_platform_detection():
    assert helpers.get_video_platform("https://www.youtube.com/watch?v=1") == "YouTube"
    assert helpers.get_video_platform("https://youtu.be/abc") == "YouTube"
    assert helpers.get_video_platform("https://www.bilibili.com/video/BV1") == "Bilibili"
    assert helpers.get_video_platform("https://example.com/video") == "其他平台"
