import json
import os

from app.services.video_processor import VideoProcessor
from app.config.settings import Config


def _make_config(temp_dir: str, output_dir: str):
    return {
        "system": {
            "temp_dir": temp_dir,
            "output_dir": output_dir,
            "audio_format": "wav",
            "audio_sample_rate": 16000,
        },
        "processing": {},
        "upload": {},
    }


def test_create_task_idempotent_for_same_url(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    vp = VideoProcessor()

    url = "https://example.com/video"
    task_id_1 = vp.create_task(url)
    task_id_2 = vp.create_task(url)

    assert task_id_1 == task_id_2


def test_cancel_flags_and_cancel_all_processing(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    vp = VideoProcessor()

    t1 = vp.create_task("https://example.com/a")
    t2 = vp.create_task("https://example.com/b")

    # 将其中一个任务标记为 processing，以便 cancel_all_processing 捕获
    task1 = vp.get_task(t1)
    task2 = vp.get_task(t2)
    task1.status = "processing"
    task2.status = "completed"

    affected = vp.cancel_all_processing()
    assert t1 in affected
    assert t2 not in affected
    assert vp._is_cancelled(t1) is True
    assert vp._is_cancelled(t2) is False


def test_save_and_load_tasks_round_trip(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    vp1 = VideoProcessor()
    url = "https://example.com/video"
    task_id = vp1.create_task(url)

    # 修改任务部分字段以验证持久化
    task = vp1.get_task(task_id)
    task.status = "completed"
    task.transcript = "hello"
    vp1.save_tasks_to_disk()

    tasks_file = os.path.join(vp1.output_dir, "tasks.json")
    assert os.path.exists(tasks_file)
    # 文件应该是一个 JSON 对象或列表，这里只做存在性和基本结构检查
    with open(tasks_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 实现当前持久化为任务列表，不强绑定顶层结构为 dict，以保持向后兼容
    assert isinstance(data, list)
    assert len(data) >= 1
    assert isinstance(data[0], dict)
    assert "id" in data[0]

    # 新实例应能从磁盘加载任务
    vp2 = VideoProcessor()
    loaded_task = vp2.get_task(task_id)
    assert loaded_task is not None
    assert loaded_task.video_url == url
    assert loaded_task.status == "completed"
    assert loaded_task.transcript == "hello"

