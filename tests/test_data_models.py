import datetime

from app.models.data_models import (
    VideoInfo,
    TranscriptionSegment,
    TranscriptionResult,
    ProcessingTask,
    UploadTask,
)


def test_transcription_result_to_dict_roundtrip():
    segments = [
        TranscriptionSegment(text="hello", confidence=0.9),
        TranscriptionSegment(text="world", confidence=0.8),
    ]
    result = TranscriptionResult(
        segments=segments,
        full_text="hello world",
        language="en",
        duration=12.34,
    )

    data = result.to_dict()

    assert data["full_text"] == "hello world"
    assert data["language"] == "en"
    assert data["duration"] == 12.34
    assert data["segments"] == [
        {"text": "hello", "confidence": 0.9},
        {"text": "world", "confidence": 0.8},
    ]


def test_processing_task_to_dict_includes_video_info_and_progress():
    info = VideoInfo(
        title="Test video",
        url="https://example.com/v",
        duration=123.0,
        uploader="uploader",
        description="desc",
    )

    created_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    task = ProcessingTask(
        id="t-1",
        video_url="https://example.com/v",
        status="processing",
        created_at=created_at,
        video_info=info,
        transcript="some text",
    )
    task.progress = 42
    task.progress_stage = "processing"
    task.progress_detail = "step"
    task.estimated_time = 10
    task.processed_segments = 2
    task.total_segments = 4

    data = task.to_dict()

    assert data["type"] == "processing"
    assert data["id"] == "t-1"
    assert data["video_url"] == "https://example.com/v"
    assert data["status"] == "processing"
    # created_at serialized as ISO string
    assert data["created_at"].startswith("2024-01-01T12:00:00")

    assert data["audio_file_path"] is None
    assert data["video_file_path"] is None

    # video_info flattened but present
    vi = data["video_info"]
    assert vi == {
        "title": "Test video",
        "url": "https://example.com/v",
        "duration": 123.0,
        "uploader": "uploader",
        "description": "desc",
    }

    assert data["transcript"] == "some text"
    assert data["progress"] == 42
    assert data["progress_stage"] == "processing"
    assert data["progress_detail"] == "step"
    assert data["estimated_time"] == 10
    assert data["processed_segments"] == 2
    assert data["total_segments"] == 4


def test_upload_task_to_dict_overrides_type_and_adds_upload_fields():
    created_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    upload_time = datetime.datetime(2024, 1, 1, 12, 5, 0)
    task = UploadTask(
        id="u-1",
        video_url="",
        status="completed",
        created_at=created_at,
        file_type="video",
        original_filename="video.mp4",
        file_size=1024,
        file_duration=10.5,
        upload_time=upload_time,
        need_audio_extraction=True,
        upload_progress=100,
        upload_status="completed",
        upload_error_message="",
    )

    data = task.to_dict()

    # type should be overridden to 'upload'
    assert data["type"] == "upload"

    assert data["file_type"] == "video"
    assert data["original_filename"] == "video.mp4"
    assert data["file_size"] == 1024
    assert data["file_duration"] == 10.5
    assert data["upload_time"].startswith("2024-01-01T12:05:00")
    assert data["need_audio_extraction"] is True
    assert data["upload_progress"] == 100
    assert data["upload_status"] == "completed"
    assert data["upload_error_message"] == ""
