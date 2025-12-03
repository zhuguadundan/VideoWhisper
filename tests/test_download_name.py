from app.utils.download_name import build_filename


def test_build_filename_strips_extension_and_normalizes_title():
    name = build_filename("my-video.mp4", "data", "json")

    # extension should be removed from title and final suffix/extension preserved
    assert name.endswith(".json")
    base = name.rsplit(".", 1)[0]
    # title part should not contain the original ".mp4" and should not contain hyphen
    title_part = base.split("_", 1)[0]
    assert "mp4" not in title_part
    assert "-" not in title_part
    assert title_part  # non-empty


def test_build_filename_uses_fallback_title_and_custom_type():
    name = build_filename("", "custom", "md")
    # empty title falls back to the generic label, but we only care about structure
    assert name.endswith("custom.md")
    assert "_custom.md" in name


def test_build_filename_truncates_long_title():
    long_title = "这是一个非常非常长的视频标题，用来测试截断行为"  # more than 20 chars
    name = build_filename(long_title, "summary", "txt")

    base = name.rsplit(".", 1)[0]
    title_part = base.split("_", 1)[0]
    # implementation truncates title to at most 20 characters
    assert len(title_part) <= 20
    assert name.endswith(".txt")
