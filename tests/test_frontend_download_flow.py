from pathlib import Path


APP_JS_PATH = (
    Path(__file__).resolve().parents[1] / "web" / "static" / "js" / "app.js"
)


def test_download_polling_handles_api_level_failures():
    source = APP_JS_PATH.read_text(encoding="utf-8")

    assert "const failDownloadSession = (message, title = '下载失败', level = 'error') => {" in source
    assert "if (!resp.ok || !pr.success)" in source
    assert "failDownloadSession(message);" in source
    assert "showToast('warning', '下载状态超时'" in source
