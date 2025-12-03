import os

from app.services.video_processor import VideoProcessor
from app.config.settings import Config
from app.models.data_models import VideoInfo, TranscriptionResult


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


def _init_vp(tmp_path, monkeypatch) -> VideoProcessor:
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    output_dir.mkdir()

    cfg = _make_config(str(temp_dir), str(output_dir))
    monkeypatch.setattr(Config, "load_config", staticmethod(lambda: cfg))
    # reset any cached config to ensure our minimal config is used
    Config._config_cache = None

    return VideoProcessor()


def test_get_task_progress_with_transcript_and_fallback(tmp_path, monkeypatch):
    vp = _init_vp(tmp_path, monkeypatch)

    # Task with explicit transcript and video_info
    tid1 = vp.create_task("https://example.com/1")
    task1 = vp.get_task(tid1)
    task1.status = "completed"
    task1.progress = 100
    task1.progress_stage = "done"
    task1.progress_detail = "all"
    task1.estimated_time = 0
    task1.processed_segments = 3
    task1.total_segments = 3
    task1.video_info = VideoInfo(
        title="Test Video",
        url="https://example.com/1",
        duration=42.0,
        uploader="uploader",
        description="desc",
    )
    task1.transcript = "hello world"

    info1 = vp.get_task_progress(tid1)
    assert info1["id"] == tid1
    assert info1["status"] == "completed"
    assert info1["progress"] == 100
    assert info1["video_title"] == "Test Video"
    assert info1["video_uploader"] == "uploader"
    assert info1["video_duration"] == 42.0
    assert info1["full_transcript"] == "hello world"
    assert info1["transcript_ready"] is True

    # Task without transcript but with transcription.full_text should fall back
    tid2 = vp.create_task("https://example.com/2")
    task2 = vp.get_task(tid2)
    task2.status = "completed"
    task2.transcript = ""  # no cleaned transcript yet
    task2.transcription = TranscriptionResult(
        segments=[],
        full_text="raw text from stt",
        language="en",
        duration=1.0,
    )

    info2 = vp.get_task_progress(tid2)
    assert info2["full_transcript"] == "raw text from stt"
    assert info2["transcript_ready"] is True

    # Unknown task should return an error structure instead of raising
    missing = vp.get_task_progress("non-existent")
    assert "error" in missing and missing["error"]


def test_translate_transcript_success_and_failure(tmp_path, monkeypatch):
    vp = _init_vp(tmp_path, monkeypatch)

    # Prepare a completed task with transcript
    tid = vp.create_task("https://example.com/vid")
    task = vp.get_task(tid)
    task.status = "completed"
    task.transcript = "some transcript text"
    task.video_info = VideoInfo(
        title="Video Title",
        url="https://example.com/vid",
        duration=10.0,
        uploader="uploader",
        description="",
    )

    class DummyTextProcessor:
        def __init__(self):  # noqa: D401
            self.runtime_config = None
            self.calls = []

        def set_runtime_config(self, cfg):  # noqa: D401
            self.runtime_config = cfg

        def get_default_provider(self):  # noqa: D401
            return "default-provider"

        def generate_bilingual_transcript(self, text, provider=None):  # noqa: D401
            self.calls.append((text, provider))
            return "BILINGUAL CONTENT"

    dummy_tp = DummyTextProcessor()
    vp.text_processor = dummy_tp

    api_cfg = {"text_processor": {"temperature": 0.1}}
    vp.translate_transcript(tid, llm_provider=None, api_config=api_cfg)

    # Text processor should have been configured and called
    assert dummy_tp.runtime_config == api_cfg["text_processor"]
    assert dummy_tp.calls == [("some transcript text", "default-provider")]

    # Task flags updated
    assert task.translation_status == "completed"
    assert task.translation_ready is True

    # Bilingual file should be written under output_dir/task_id
    task_dir = os.path.join(vp.output_dir, tid)
    files = [f for f in os.listdir(task_dir) if f.startswith("transcript_bilingual_")]
    assert files, "expected bilingual transcript file to be created"

    # Failure branch: generation error should mark status failed and propagate
    tid2 = vp.create_task("https://example.com/vid2")
    task2 = vp.get_task(tid2)
    task2.status = "completed"
    task2.transcript = "text to fail"

    class FailingTP(DummyTextProcessor):
        def generate_bilingual_transcript(self, text, provider=None):  # noqa: D401
            raise RuntimeError("boom")

    failing_tp = FailingTP()
    vp.text_processor = failing_tp

    try:
        vp.translate_transcript(tid2, llm_provider="prov", api_config=None)
        assert False, "expected translate_transcript to raise on failure"
    except RuntimeError:
        # task flags should reflect failure
        assert task2.translation_status == "failed"
        assert task2.translation_ready is False
        assert "翻译失败" in task2.error_message
