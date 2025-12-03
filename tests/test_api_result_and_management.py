import os
import types

import pytest

import app.main as main


def test_translate_requires_body_and_task_id(client):
    # Empty JSON, missing task_id
    resp = client.post("/api/translate", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_translate_bilingual_happy_path(client, monkeypatch):
    calls = {}

    def fake_translate(task_id, llm_provider, api_config):  # noqa: D401
        calls["args"] = (task_id, llm_provider, api_config)

    # Replace global video_processor with a simple stub for this test
    monkeypatch.setattr(
        main,
        "video_processor",
        types.SimpleNamespace(translate_transcript=fake_translate),
    )

    # Replace threading.Thread so we can run the target synchronously
    class DummyThread:
        def __init__(self, target, daemon=None):  # noqa: D401
            self._target = target
            self.daemon = daemon

        def start(self):  # noqa: D401
            # run inline to keep test deterministic
            self._target()

    monkeypatch.setattr(main, "threading", types.SimpleNamespace(Thread=DummyThread))

    payload = {"task_id": "t-1", "llm_provider": "prov", "api_config": {"a": 1}}
    resp = client.post("/api/translate", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["task_id"] == "t-1"

    assert calls["args"] == ("t-1", "prov", {"a": 1})


def test_get_result_missing_and_not_completed(client, monkeypatch):
    # Missing task
    monkeypatch.setattr(main.video_processor, "get_task", lambda tid: None)
    resp = client.get("/api/result/unknown")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False

    # Task exists but not completed
    task = types.SimpleNamespace(status="processing")
    monkeypatch.setattr(main.video_processor, "get_task", lambda tid: task)
    resp2 = client.get("/api/result/abc")
    assert resp2.status_code == 400
    data2 = resp2.get_json()
    assert data2["success"] is False


def test_get_result_completed_with_and_without_translation(tmp_path, client, monkeypatch):
    from app.models.data_models import VideoInfo

    # Completed task without translation, transcript should be returned
    task_id = "t-ok"
    task = types.SimpleNamespace(
        id=task_id,
        status="completed",
        video_info=VideoInfo(
            title="Test Video",
            url="https://example.com/v",
            duration=10.0,
            uploader="u",
            description="",
        ),
        video_url="https://example.com/v",
        transcript="plain transcript",
        summary={"s": "v"},
        analysis={"k": 1},
        translation_ready=False,
    )

    monkeypatch.setattr(main.video_processor, "get_task", lambda tid: task)
    resp = client.get(f"/api/result/{task_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["video_info"]["title"] == "Test Video"
    assert data["data"]["transcript"] == "plain transcript"

    # Completed task with translation_ready and a bilingual file on disk
    task_id2 = "t-trl"
    task2 = types.SimpleNamespace(
        id=task_id2,
        status="completed",
        video_info=None,
        video_url="https://example.com/v2",
        transcript="original transcript",
        summary={},
        analysis={},
        translation_ready=True,
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(main.video_processor, "output_dir", str(out_dir))
    monkeypatch.setattr(main.video_processor, "get_task", lambda tid: task2)

    task_dir = out_dir / task_id2
    task_dir.mkdir()
    bilingual_path = task_dir / "transcript_bilingual_test.md"
    bilingual_text = "BILINGUAL CONTENT"
    bilingual_path.write_text(bilingual_text, encoding="utf-8")

    resp2 = client.get(f"/api/result/{task_id2}")
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2["success"] is True
    assert data2["data"]["transcript"] == bilingual_text


def test_download_file_requires_completed_task_and_supports_transcript(tmp_path, client, monkeypatch):
    from app.models.data_models import VideoInfo

    # Task not found or not completed -> generic failure
    monkeypatch.setattr(main.video_processor, "get_task", lambda tid: None)
    resp = client.get("/api/download/nope/transcript")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is False

    # Unsupported file_type -> explicit error
    task = types.SimpleNamespace(status="completed", video_info=None)
    monkeypatch.setattr(main.video_processor, "get_task", lambda tid: task)
    resp2 = client.get("/api/download/t1/unknown")
    assert resp2.status_code == 200
    assert resp2.get_json()["success"] is False

    # Happy path: transcript download
    task_id = "t-dl"
    task3 = types.SimpleNamespace(
        id=task_id,
        status="completed",
        video_info=VideoInfo(
            title="Video Title",
            url="https://example.com/v",
            duration=10.0,
            uploader="u",
            description="",
        ),
    )
    monkeypatch.setattr(main.video_processor, "get_task", lambda tid: task3)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(main.video_processor, "output_dir", str(out_dir))

    task_dir = out_dir / task_id
    task_dir.mkdir()
    # Create a bilingual transcript so it is preferred
    file_path = task_dir / "transcript_bilingual_demo.md"
    file_path.write_text("content", encoding="utf-8")

    resp3 = client.get(f"/api/download/{task_id}/transcript")
    assert resp3.status_code == 200
    # send_file, not JSON
    assert resp3.mimetype == "text/markdown"
    cd = resp3.headers.get("Content-Disposition", "")
    assert "filename=" in cd


def test_list_tasks_returns_sorted_data(client, monkeypatch):
    from datetime import datetime, timedelta

    base = datetime(2024, 1, 1, 12, 0, 0)

    task_old = types.SimpleNamespace(
        id="t-old",
        video_url="https://example.com/old",
        status="completed",
        progress=100,
        video_info=None,
        created_at=base,
        error_message="",
    )
    task_new = types.SimpleNamespace(
        id="t-new",
        video_url="https://example.com/new",
        status="processing",
        progress=10,
        video_info=None,
        created_at=base + timedelta(minutes=5),
        error_message="",
    )

    monkeypatch.setattr(
        main.video_processor,
        "tasks",
        {task_old.id: task_old, task_new.id: task_new},
        raising=False,
    )

    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    ids = [t["id"] for t in data["data"]]
    # Newest first
    assert ids == ["t-new", "t-old"]


def test_list_files_includes_output_and_temp_files(tmp_path, client, monkeypatch):
    # Point processor dirs to temp paths
    out_dir = tmp_path / "out"
    temp_dir = tmp_path / "temp"
    out_dir.mkdir()
    temp_dir.mkdir(exist_ok=True)

    monkeypatch.setattr(main.video_processor, "output_dir", str(out_dir))
    monkeypatch.setattr(main.video_processor, "temp_dir", str(temp_dir))

    # Prepare one output file under a task id and one temp file
    task_id = "t1"
    task_dir = out_dir / task_id
    task_dir.mkdir()
    summary_file = task_dir / "summary_report.md"
    summary_file.write_text("summary", encoding="utf-8")

    temp_file = temp_dir / "temp_audio.wav"
    temp_file.write_bytes(b"data")

    # Stub get_task so file listing can resolve task title
    task = types.SimpleNamespace(id=task_id, video_info=None)
    monkeypatch.setattr(main.video_processor, "get_task", lambda tid: task)

    resp = client.get("/api/files")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True

    ids = {f["id"] for f in body["data"]}
    assert f"{task_id}/summary_report.md" in ids
    assert "temp/temp_audio.wav" in ids


def test_delete_task_files_uses_filemanager_and_updates_tasks(tmp_path, client, monkeypatch):
    from app.services.file_manager import FileManager

    # Admin protection: configure token and production env
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("FLASK_ENV", "production")

    # Prepare a stub FileManager
    class DummyFM(FileManager):
        def __init__(self):  # noqa: D401
            pass

        def delete_output_task_dir(self, task_id):  # noqa: D401
            self.last_deleted = task_id
            return True

    monkeypatch.setattr(main, "FileManager", DummyFM)

    # Prepare video_processor tasks
    task_id = "t-del"
    main.video_processor.tasks[task_id] = types.SimpleNamespace()

    # Avoid touching real disk
    monkeypatch.setattr(main.video_processor, "save_tasks_to_disk", lambda: None)

    resp = client.post(
        f"/api/files/delete-task/{task_id}",
        headers={"X-Admin-Token": "secret"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert task_id not in main.video_processor.tasks


def test_stop_all_tasks_marks_processing_failed(client, monkeypatch):
    # Admin protection
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("FLASK_ENV", "production")

    t1 = "task-processing"
    t2 = "task-completed"

    task1 = types.SimpleNamespace(
        id=t1,
        status="processing",
        progress=50,
        progress_stage="processing",
        progress_detail="...",
        error_message="",
    )
    task2 = types.SimpleNamespace(
        id=t2,
        status="completed",
        progress=100,
        progress_stage="done",
        progress_detail="",
        error_message="",
    )

    main.video_processor.tasks[t1] = task1
    main.video_processor.tasks[t2] = task2

    # cancel_all_processing should return both ids, but handler only flips those still processing
    monkeypatch.setattr(
        main.video_processor,
        "cancel_all_processing",
        lambda: [t1, t2],
    )
    monkeypatch.setattr(main.video_processor, "save_tasks_to_disk", lambda: None)

    resp = client.post(
        "/api/stop-all-tasks",
        headers={"X-Admin-Token": "secret"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert t1 in data["data"]["stopped_tasks"]

    # task1 should be marked failed; task2 untouched
    assert task1.status == "failed"
    # error_message should be a non-empty string
    assert isinstance(task1.error_message, str) and task1.error_message
    assert "用户手动停止" in task1.error_message
    assert task2.status == "completed"


def test_stop_all_tasks_when_no_processing(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("FLASK_ENV", "production")

    # No processing tasks
    monkeypatch.setattr(main.video_processor, "cancel_all_processing", lambda: [])

    resp = client.post(
        "/api/stop-all-tasks",
        headers={"X-Admin-Token": "secret"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["stopped_tasks"] == []


def test_delete_task_record_uses_filemanager_and_cleans_memory(client, monkeypatch):
    # Admin protection
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("FLASK_ENV", "production")

    class DummyFM:
        def __init__(self):  # noqa: D401
            self.deleted = []

        def delete_output_task_dir(self, task_id):  # noqa: D401
            self.deleted.append(task_id)
            return True

        def cleanup_task_files(self, task_id):  # noqa: D401
            self.deleted.append(f"temp:{task_id}")

    monkeypatch.setattr(main, "FileManager", DummyFM)

    task_id = "t-rec"
    main.video_processor.tasks[task_id] = types.SimpleNamespace()
    monkeypatch.setattr(main.video_processor, "save_tasks_to_disk", lambda: None)

    resp = client.post(
        f"/api/tasks/delete/{task_id}",
        headers={"X-Admin-Token": "secret"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert task_id not in main.video_processor.tasks
