import app.main as main


def test_video_info_requires_body_and_url(client):
    # No JSON body
    resp = client.post("/api/video-info")
    assert resp.status_code == 400

    # Empty JSON, missing video_url
    resp2 = client.post("/api/video-info", json={})
    assert resp2.status_code == 400


def test_video_info_rejects_unsafe_url(client):
    # Private/localhost URL should be rejected by SSRF guard
    resp = client.post("/api/video-info", json={"video_url": "http://127.0.0.1/test"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_video_info_success_flow(client, monkeypatch):
    def fake_get_video_info(url):
        return {"url": url, "title": "Test"}

    monkeypatch.setattr(main.video_downloader, "get_video_info", fake_get_video_info)

    resp = client.post(
        "/api/video-info", json={"video_url": "https://example.com/video"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["title"] == "Test"


def test_process_video_requires_body_and_url(client):
    resp = client.post("/api/process")
    assert resp.status_code == 400

    resp2 = client.post("/api/process", json={})
    assert resp2.status_code == 400


def test_process_video_rejects_unsafe_url(client):
    payload = {"video_url": "http://127.0.0.1/test"}
    resp = client.post("/api/process", json=payload)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_process_video_success_flow_spawns_task(client, monkeypatch):
    # Avoid heavy processing by mocking VideoProcessor methods
    monkeypatch.setattr(
        main.video_processor,
        "create_task",
        lambda url, youtube_cookies=None: "task-123",
    )
    monkeypatch.setattr(
        main.video_processor, "process_video", lambda *args, **kwargs: None
    )

    payload = {"video_url": "https://example.com/video"}
    resp = client.post("/api/process", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["task_id"] == "task-123"


def test_get_progress_returns_data(client, monkeypatch):
    def fake_get_task_progress(task_id):
        return {"status": "processing", "progress": 50}

    monkeypatch.setattr(
        main.video_processor, "get_task_progress", fake_get_task_progress
    )

    resp = client.get("/api/progress/abc")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["status"] == "processing"
    assert data["data"]["progress"] == 50


def test_downloads_create_requires_body_and_url(client):
    # No JSON body
    resp = client.post("/api/downloads")
    assert resp.status_code == 400

    # Empty JSON
    resp2 = client.post("/api/downloads", json={})
    assert resp2.status_code == 400


def test_downloads_create_rejects_unsafe_url(client):
    resp = client.post("/api/downloads", json={"url": "http://127.0.0.1/test"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_downloads_create_spawns_task(client, monkeypatch):
    monkeypatch.setattr(
        main.video_processor,
        "create_task",
        lambda url, youtube_cookies=None, bilibili_cookies=None: "task-dl-1",
    )
    monkeypatch.setattr(
        main.video_processor, "download_video_only", lambda *args, **kwargs: None
    )

    resp = client.post("/api/downloads", json={"url": "https://example.com/video"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["task_id"] == "task-dl-1"
