import os

import pytest

from app.utils.path_safety import is_within, safe_join


def test_is_within_true_for_child(tmp_path):
    base = tmp_path
    child = tmp_path / "sub" / "file.txt"
    child.parent.mkdir(parents=True)
    child.write_text("test", encoding="utf-8")

    assert is_within(str(base), str(child)) is True


def test_is_within_false_for_outside(tmp_path):
    base = tmp_path / "base"
    outside = tmp_path / "outside" / "file.txt"
    base.mkdir()
    outside.parent.mkdir()
    outside.write_text("x", encoding="utf-8")

    assert is_within(str(base), str(outside)) is False


def test_safe_join_normal_path(tmp_path):
    base = tmp_path
    (base / "dir").mkdir()
    joined = safe_join(str(base), "dir/test.txt")
    assert joined.startswith(str(base))
    assert joined.endswith(os.path.join("dir", "test.txt"))


def test_safe_join_rejects_traversal(tmp_path):
    base = tmp_path / "root"
    base.mkdir()

    with pytest.raises(ValueError):
        safe_join(str(base), "../outside.txt")

