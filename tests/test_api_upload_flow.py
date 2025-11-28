import io

import app.main as main
from app.models.data_models import UploadTask


def test_upload_requires_file_field(client):
    resp = client.post("/api/upload")
    data = resp.get_json()
    # upload_file uses safe_json_response for this branch
    assert resp.status_code == 200
    assert data["success"] is False


def test_upload_happy_path(client, monkeypatch):
    # Mock FileUploader behaviour to avoid touching real disk logic
    def fake_get_file_info(filename, size):
        return {
            "file_type": "video",
            "file_ext": "mp4",
            "mime_type": "video/mp4",
            "need_audio_extraction": True,
            "file_size": size,
        }

    def fake_validate_file(filename, size, mime):
        return True, ""

    def fake_save_uploaded_file(file_obj, original_filename, file_size, chunk_size=None):
        return {"success": True, "file_path": "/tmp/test.mp4", "file_duration": 12.3}

    monkeypatch.setattr(main.file_uploader, "_get_file_info", fake_get_file_info)
    monkeypatch.setattr(main.file_uploader, "_validate_file", fake_validate_file)
    monkeypatch.setattr(main.file_uploader, "save_uploaded_file", fake_save_uploaded_file)

    monkeypatch.setattr(main.video_processor, "create_upload_task", lambda **kwargs: "u-1")
    monkeypatch.setattr(main.video_processor, "fail_upload_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.video_processor, "complete_upload_task", lambda *args, **kwargs: None)

    data = {"file": (io.BytesIO(b"hello"), "video.mp4")}
    resp = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["task_id"] == "u-1"


def test_get_upload_progress_success(client, monkeypatch):
    task = UploadTask(
        id="u-1",
        video_url="",
        file_type="video",
        original_filename="video.mp4",
        file_size=123,
        upload_status="completed",
        upload_progress=100,
    )

    monkeypatch.setattr(main.video_processor, "get_task", lambda task_id: task)

    resp = client.get("/api/upload/u-1/progress")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["task_id"] == "u-1"
    assert data["data"]["upload_status"] == "completed"
    assert data["data"]["upload_progress"] == 100


def test_process_upload_requires_completed_status(client, monkeypatch):
    # Task exists but not completed yet
    task = UploadTask(
        id="u-2",
        video_url="",
        file_type="video",
        original_filename="video2.mp4",
        file_size=123,
        upload_status="uploading",
        upload_progress=50,
    )

    monkeypatch.setattr(main.video_processor, "get_task", lambda task_id: task)

    resp = client.post(
        "/api/process-upload",
        json={"task_id": "u-2", "llm_provider": "openai", "api_config": {}},
    )
    # ValueError -> handled by api_error_handler
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_process_upload_success_spawns_background_processing(client, monkeypatch):
    task = UploadTask(
        id="u-3",
        video_url="",
        file_type="video",
        original_filename="video3.mp4",
        file_size=123,
        upload_status="completed",
        upload_progress=100,
    )

    monkeypatch.setattr(main.video_processor, "get_task", lambda task_id: task)
    monkeypatch.setattr(main.video_processor, "process_upload", lambda *args, **kwargs: None)

    resp = client.post(
        "/api/process-upload",
        json={"task_id": "u-3", "llm_provider": "openai", "api_config": {}},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["task_id"] == "u-3"


def test_get_upload_config_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        main.file_uploader,
        "get_upload_config",
        lambda: {"max_size_mb": 100, "allowed": ["mp4"]},
    )

    resp = client.get("/api/upload/config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["max_size_mb"] == 100

