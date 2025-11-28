import os
import uuid

from app.services.file_manager import FileManager
from app.config.settings import Config


def _make_config(temp_dir: str, output_dir: str):
    return {
        "system": {
            "temp_dir": temp_dir,
            "output_dir": output_dir,
        }
    }


def test_register_task_and_history_truncation(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(Config, "get_config", staticmethod(lambda: _make_config(str(temp_dir), str(output_dir))))

    fm = FileManager()

    # 注册多个任务，超过 max_temp_tasks=3，看是否被截断
    task_ids = [str(uuid.uuid4()) for _ in range(5)]
    for tid in task_ids:
        fake_file = temp_dir / f"{tid}.tmp"
        fake_file.write_text("x", encoding="utf-8")
        fm.register_task(tid, [str(fake_file)], register_dir=True)

    history = fm.get_task_history()
    assert len(history) <= fm.max_temp_tasks
    # 最新的几个任务 id 应该还在历史里
    remaining_ids = {h["task_id"] for h in history}
    assert set(task_ids[-3:]).issubset(remaining_ids)


def test_cleanup_task_files_removes_files_and_history(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(Config, "get_config", staticmethod(lambda: _make_config(str(temp_dir), str(output_dir))))

    fm = FileManager()
    task_id = str(uuid.uuid4())

    # 创建任务相关文件
    task_temp_dir = temp_dir / task_id
    task_temp_dir.mkdir()
    file1 = task_temp_dir / "a.txt"
    file2 = task_temp_dir / "b.txt"
    file1.write_text("1", encoding="utf-8")
    file2.write_text("2", encoding="utf-8")

    fm.register_task(task_id, [str(file1), str(file2)], register_dir=True)

    # 清理任务
    fm.cleanup_task_files(task_id)

    assert not file1.exists()
    assert not file2.exists()
    # 目录也应该被删除
    assert not task_temp_dir.exists()

    # 历史记录中不应再有该任务
    history_after = fm.get_task_history()
    assert all(h.get("task_id") != task_id for h in history_after)


def test_cleanup_task_files_does_not_remove_temp_dir_for_invalid_uuid(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(Config, "get_config", staticmethod(lambda: _make_config(str(temp_dir), str(output_dir))))

    fm = FileManager()
    task_id = "not-a-uuid"

    task_temp_dir = temp_dir / task_id
    task_temp_dir.mkdir()
    file_path = task_temp_dir / "file.txt"
    file_path.write_text("x", encoding="utf-8")

    # 注册一个带非法 task_id 的任务
    fm.register_task(task_id, [str(file_path)], register_dir=True)

    fm.cleanup_task_files(task_id)

    # 文件会被删除，但目录由于 _is_valid_task_id 失败不会被删除
    assert not file_path.exists()
    assert task_temp_dir.exists()


def test_delete_output_task_dir_valid_and_invalid_ids(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(Config, "get_config", staticmethod(lambda: _make_config(str(temp_dir), str(output_dir))))

    fm = FileManager()

    # 有效 UUID 对应的目录应被删除
    valid_id = str(uuid.uuid4())
    valid_dir = output_dir / valid_id
    valid_dir.mkdir()
    (valid_dir / "result.txt").write_text("ok", encoding="utf-8")

    assert fm.delete_output_task_dir(valid_id) is True
    assert not valid_dir.exists()

    # 非法 id 不会尝试删除
    assert fm.delete_output_task_dir("not-a-uuid") is False

