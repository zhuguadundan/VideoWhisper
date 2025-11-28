import os

import app.main as main


def test_download_managed_file_success(client):
    # Prepare a file in the output directory used by VideoProcessor
    output_dir = main.video_processor.output_dir
    task_id = "task1"
    task_dir = os.path.join(output_dir, task_id)
    os.makedirs(task_dir, exist_ok=True)
    file_name = "result.txt"
    file_path = os.path.join(task_dir, file_name)
    content = b"hello download"
    with open(file_path, "wb") as f:
        f.write(content)

    file_id = f"{task_id}/{file_name}"
    resp = client.get(f"/api/files/download/{file_id}")
    assert resp.status_code == 200
    assert resp.data == content
    # Content-Disposition should contain the filename
    cd = resp.headers.get("Content-Disposition", "")
    assert "result.txt" in cd


def test_download_managed_file_rejects_traversal(client):
    # Task id is valid but the file part attempts traversal
    file_id = "task1/../evil.txt"
    resp = client.get(f"/api/files/download/{file_id}")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_delete_files_requires_admin_token(client, monkeypatch):
    # Configure admin protection
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("FLASK_ENV", "production")

    # Prepare a file to delete
    output_dir = main.video_processor.output_dir
    task_id = "task2"
    task_dir = os.path.join(output_dir, task_id)
    os.makedirs(task_dir, exist_ok=True)
    file_name = "to_delete.txt"
    file_path = os.path.join(task_dir, file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("x")

    file_id = f"{task_id}/{file_name}"

    # Missing header -> 403
    resp_forbidden = client.post("/api/files/delete", json={"file_ids": [file_id]})
    assert resp_forbidden.status_code == 403

    # With correct header -> file removed
    resp = client.post(
        "/api/files/delete",
        json={"file_ids": [file_id]},
        headers={"X-Admin-Token": "secret"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["deleted_count"] == 1
    assert not os.path.exists(file_path)

