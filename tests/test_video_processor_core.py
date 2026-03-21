import json
import os

from app.models.data_models import VideoInfo
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


def test_create_task_creates_distinct_ids_for_same_url(tmp_path, monkeypatch):
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

    assert task_id_1 != task_id_2


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
    task.video_file_path = os.path.join(vp1.output_dir, task_id, "video.mp4")
    task.progress = 88
    task.progress_stage = "保存结果"
    task.progress_detail = "准备写入文件"
    task.estimated_time = 5
    task.processed_segments = 3
    task.total_segments = 4
    task.transcript_ready = True
    task.translation_status = "completed"
    task.translation_ready = True
    task.ai_response_times = {"transcript": 1.2, "summary": 2.3}
    task.download_format = "137+140"
    task.video_info = VideoInfo(
        title="Loaded Video",
        url=url,
        duration=12.0,
        uploader="tester",
        description="desc",
    )
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
    assert loaded_task.video_file_path == task.video_file_path
    assert loaded_task.progress == 88
    assert loaded_task.progress_stage == "保存结果"
    assert loaded_task.progress_detail == "准备写入文件"
    assert loaded_task.estimated_time == 5
    assert loaded_task.processed_segments == 3
    assert loaded_task.total_segments == 4
    assert loaded_task.transcript_ready is True
    assert loaded_task.translation_status == "completed"
    assert loaded_task.translation_ready is True
    assert loaded_task.ai_response_times == {"transcript": 1.2, "summary": 2.3}
    assert loaded_task.download_format == "137+140"
    assert loaded_task.video_info.description == "desc"


def test_video_processor_init_cleans_stale_partial_download_dirs(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))
    Config._config_cache = None

    task_id = "9df6bb8c-df3b-414d-a2ff-9f9e0cd6f3f2"
    partial_dir = output_dir / task_id / ".partial"
    partial_dir.mkdir(parents=True)
    (partial_dir / "stale.part").write_text("stale", encoding="utf-8")

    tasks_file = output_dir / "tasks.json"
    tasks_file.write_text(
        json.dumps(
            [
                {
                    "id": task_id,
                    "video_url": "https://example.com/video",
                    "status": "failed",
                    "created_at": "2026-03-15T15:00:00",
                    "error_message": "boom",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    VideoProcessor()

    assert not partial_dir.exists()


def test_step_get_video_info_uses_site_specific_cookies(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    vp = VideoProcessor()
    task_id = vp.create_task(
        "https://www.bilibili.com/video/BV1xx411c7mD",
        bilibili_cookies="SESSDATA=abc",
    )
    task = vp.get_task(task_id)
    captured = {}

    def fake_get_video_info(url, cookies_str=None, *, cookies_domain=None):
        captured["url"] = url
        captured["cookies_str"] = cookies_str
        captured["cookies_domain"] = cookies_domain
        return {
            "title": "Bili Video",
            "url": url,
            "duration": 12,
            "uploader": "tester",
        }

    monkeypatch.setattr(vp.video_downloader, "get_video_info", fake_get_video_info)

    info = vp._step_get_video_info(task_id, task)

    assert info["title"] == "Bili Video"
    assert captured["url"] == task.video_url
    assert captured["cookies_str"] == "SESSDATA=abc"
    assert captured["cookies_domain"] == ".bilibili.com"


def test_download_video_only_skips_duplicate_start_when_task_is_processing(
    tmp_path, monkeypatch
):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    vp = VideoProcessor()
    task_id = vp.create_task("https://example.com/video")
    task = vp.get_task(task_id)
    task.status = "processing"

    def fail_if_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("duplicate download start should not reach downloader")

    monkeypatch.setattr(vp, "_step_get_video_info", fail_if_called)

    result = vp.download_video_only(task_id)

    assert result is task
    assert task.status == "processing"


def test_process_video_skips_duplicate_start_when_task_is_processing(
    tmp_path, monkeypatch
):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    vp = VideoProcessor()
    task_id = vp.create_task("https://example.com/video")
    task = vp.get_task(task_id)
    task.status = "processing"

    def fail_if_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("duplicate processing start should not build services")

    monkeypatch.setattr(vp, "_create_speech_to_text_service", fail_if_called)

    result = vp.process_video(task_id)

    assert result is task
    assert task.status == "processing"


def test_download_video_only_clears_stale_error_on_success(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    vp = VideoProcessor()
    task_id = vp.create_task("https://example.com/video")
    task = vp.get_task(task_id)
    task.error_message = "stale error"

    final_dir = output_dir / task_id
    final_dir.mkdir()
    final_path = final_dir / "video.mp4"
    final_path.touch()

    monkeypatch.setattr(
        vp,
        "_step_get_video_info",
        lambda current_task_id, current_task: {
            "title": "Video",
            "url": current_task.video_url,
            "duration": 10,
            "uploader": "tester",
        },
    )
    monkeypatch.setattr(
        vp.video_downloader,
        "download_video",
        lambda *args, **kwargs: str(final_path),
    )

    result = vp.download_video_only(task_id)

    assert result.status == "completed"
    assert result.error_message == ""
    assert result.video_file_path == str(final_path)


def test_process_upload_skips_duplicate_start_when_task_is_processing(
    tmp_path, monkeypatch
):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    vp = VideoProcessor()
    task_id = vp.create_upload_task("audio.mp3", 123, "audio", "audio/mpeg")
    task = vp.get_task(task_id)
    task.upload_status = "completed"
    task.status = "processing"
    task.audio_file_path = str(temp_dir / "audio.mp3")

    def fail_if_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("duplicate upload processing should not build services")

    monkeypatch.setattr(vp, "_create_speech_to_text_service", fail_if_called)

    result = vp.process_upload(task_id)

    assert result is task
    assert task.status == "processing"


def test_process_upload_clears_stale_error_on_success(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))

    vp = VideoProcessor()
    task_id = vp.create_upload_task("audio.mp3", 123, "audio", "audio/mpeg")
    task = vp.get_task(task_id)
    task.upload_status = "completed"
    task.audio_file_path = str(temp_dir / "audio.mp3")
    task.error_message = "stale error"

    class _NoTextProvider:
        def get_available_providers(self):
            return []

    monkeypatch.setattr(vp, "_create_speech_to_text_service", lambda api_config=None: object())
    monkeypatch.setattr(vp, "_create_text_processor_service", lambda api_config=None: _NoTextProvider())
    monkeypatch.setattr(
        vp.file_uploader,
        "get_file_info_from_path",
        lambda path: {"duration": 10, "file_size": 123},
    )
    monkeypatch.setattr(
        vp.audio_extractor,
        "get_audio_info",
        lambda path: {"duration": 10},
    )
    monkeypatch.setattr(
        vp,
        "_step_process_audio_and_transcribe",
        lambda *args, **kwargs: ("hello", [], "en", {"duration": 10}),
    )
    monkeypatch.setattr(vp, "_save_results", lambda current_task: None)
    monkeypatch.setattr(
        vp,
        "_smart_cleanup_temp_files",
        lambda current_task_id, audio_path: None,
    )

    result = vp.process_upload(task_id)

    assert result.status == "completed"
    assert result.error_message == ""
